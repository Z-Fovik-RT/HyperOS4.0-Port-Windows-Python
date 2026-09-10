import logging
import re
from pathlib import Path
from typing import List, Optional


class XmlUtils:
    def __init__(self):
        self.logger = logging.getLogger("XmlUtils")

    def get_res_dir(self, work_dir: Path) -> Path:
        """
        Smartly retrieve real res directory.
        Compatible with APKEditor (resources/package_*/res/) and Apktool (res/).
        """
        possible_res_dirs = []

        # 1. Collect standard res directory from Apktool or normal APK
        standard_res = work_dir / "res"
        if standard_res.exists():
            possible_res_dirs.append(standard_res)

        # 2. Collect res directory from APKEditor multi-package structure
        resources_dir = work_dir / "resources"
        if resources_dir.exists() and resources_dir.is_dir():
            for pkg_dir in resources_dir.glob("package_*"):
                pkg_res = pkg_dir / "res"
                if pkg_res.exists():
                    possible_res_dirs.append(pkg_res)

        # 3. Ultimate radar: Search for directory containing values/strings.xml among all candidates
        for res in possible_res_dirs:
            if (res / "values" / "strings.xml").exists() or (res / "values" / "arrays.xml").exists():
                self.logger.debug(f"Targeting resource directory: {res.relative_to(work_dir)}")
                return res

        # 4. Fallback: If not found (e.g. minimal APP with no strings), return the first found or standard res/
        if possible_res_dirs:
            return possible_res_dirs[0]
            
        return work_dir / "res"

    def get_id(self, res_dir: Path, name: str) -> Optional[str]:
        """Get resource ID from public.xml"""
        if not res_dir: return None
        public_xml = res_dir / "values/public.xml"
        if not public_xml.exists(): return None

        content = public_xml.read_text(encoding='utf-8', errors='ignore')
        
        # Robust lookup handling arbitrary attribute order
        pattern = re.compile(f'<public[^>]+name="{re.escape(name)}"[^>]*>', re.DOTALL)
        match = pattern.search(content)
        if match:
            tag_text = match.group(0)
            id_match = re.search(r'id="(0x[0-9a-fA-F]+)"', tag_text)
            if id_match:
                return id_match.group(1)
                
        return None
    
    def add_string(self, res_dir: Path, name: str, value: str, lang_suffix: str = ""):
        """
        Inject string into strings.xml and automatically register valid resource ID in public.xml
        :param lang_suffix: Language suffix, e.g. "zh-rCN" (corresponds to values-zh-rCN), empty for default values
        """
        if not res_dir: return
        
        # Auto-register Public ID to prevent APKEditor errors
        self.add_public_id(res_dir, "string", name)

        target_dir = None
        if not lang_suffix:
            exact_dir = res_dir / "values"
            if exact_dir.exists() and exact_dir.is_dir():
                target_dir = exact_dir
        else:
            dir_name = f"values-{lang_suffix}"
            for d in res_dir.iterdir():
                if d.is_dir() and (d.name == dir_name or d.name.startswith(f"{dir_name}-")):
                    target_dir = d
                    break
        
        if not target_dir:
            if not lang_suffix: 
                target_dir = res_dir / "values" 
                target_dir.mkdir(parents=True, exist_ok=True) 
            else: 
                return 

        target_file = target_dir / "strings.xml"
        if not target_file.exists():
            self.logger.info(f"File {target_file.name} not found in {target_dir.name}, creating a new one.")
            empty_xml = '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n</resources>\n'
            target_file.write_text(empty_xml, encoding='utf-8', newline='\n')

        content = target_file.read_text(encoding='utf-8', errors='ignore')
        if f'name="{name}"' in content:
            self.logger.warning(f"String '{name}' already exists in {target_dir.name}/{target_file.name}, skipping.") 
            return

        new_line = f'\n    <string name="{name}">{value}</string>\n'
        parts = content.rsplit('</resources>', 1)
        
        if len(parts) == 2:
            new_content = parts[0] + new_line + '</resources>\n'
            target_file.write_text(new_content, encoding='utf-8', newline='\n')
            self.logger.debug(f"Injected string '{name}' into {target_dir.name}")
        else:
            self.logger.error(f"Failed to find </resources> tag in {target_file.name}") 

    def add_public_id(self, res_dir: Path, res_type: str, name: str) -> Optional[str]:
        """
        向 public.xml 注册新 ID (自动增长，无视属性顺序)
        """
        if not res_dir: return None
        public_xml = res_dir / "values/public.xml"
        if not public_xml.exists(): return None

        content = public_xml.read_text(encoding='utf-8', errors='ignore')
        
        # 1. 检查是否已存在
        if f'name="{name}"' in content:
            match = re.search(rf'<public[^>]*name="{name}"[^>]*id="(0x[0-9a-fA-F]+)"', content)
            if match:
                return match.group(1)

        # 2. 计算新 ID
        ids = []
        for match in re.finditer(r'<public([^>]+)>', content):
            attrs = match.group(1)
            if f'type="{res_type}"' in attrs:
                id_match = re.search(r'id="(0x[0-9a-fA-F]+)"', attrs)
                if id_match:
                    ids.append(int(id_match.group(1), 16))
        
        if not ids:
            if res_type == "string": new_id_int = 0x7f100000
            elif res_type == "id": new_id_int = 0x7f0b0000
            else: new_id_int = 0x7f010000 
        else:
            new_id_int = max(ids) + 1
        
        new_id_hex = f"0x{new_id_int:x}"
        
        # 3. 插入新 ID
        line = f'\n    <public type="{res_type}" name="{name}" id="{new_id_hex}" />\n'
        parts = content.rsplit('</resources>', 1)
        if len(parts) == 2:
            new_content = parts[0] + line + '</resources>\n'
            public_xml.write_text(new_content, encoding='utf-8', newline='\n')
        else:
            new_content = content.replace('</resources>', f'{line}</resources>')
            public_xml.write_text(new_content, encoding='utf-8')
        
        self.logger.info(f"Generated Public ID for {name}: {new_id_hex}")
        return new_id_hex

    def add_array_item(self, res_dir: Path, array_name: str, items: List[str], lang_suffix: str = ""):
        """
        向 arrays.xml 中的指定数组批量追加多个 <item>
        """
        if not res_dir or not items: 
            return

        target_dir = None
        if not lang_suffix:
            exact_dir = res_dir / "values"
            if exact_dir.exists() and exact_dir.is_dir():
                target_dir = exact_dir
        else:
            dir_name = f"values-{lang_suffix}"
            for d in res_dir.iterdir():
                if d.is_dir() and (d.name == dir_name or d.name.startswith(f"{dir_name}-")):
                    target_dir = d
                    break

        if not target_dir:
            if not lang_suffix:
                target_dir = res_dir / "values"
            else:
                return

        target_file = target_dir / "arrays.xml"
        if not target_file.exists():
            target_file = target_dir / "strings.xml"
            if not target_file.exists():
                return

        content = target_file.read_text(encoding='utf-8', errors='ignore')

        pattern = re.compile(
            rf'(<(?P<tag>string-array|integer-array|array)\s+name="{array_name}"[^>]*>)(.*?)(</(?P=tag)>)', 
            re.DOTALL
        )
        
        match = pattern.search(content)
        if not match:
            self.logger.warning(f"Array '{array_name}' not found in {target_dir.name}/{target_file.name}")
            return
            
        open_tag = match.group(1)      
        inner_content = match.group(3) 
        close_tag = match.group(4)     
        
        added_count = 0
        new_inner = inner_content
        for item in items:
            if f'>{item}</item>' not in new_inner:
                new_inner += f'\n        <item>{item}</item>'
                added_count += 1
                
        if added_count == 0:
            return
            
        if not new_inner.endswith('\n'):
            new_inner += '\n    '
        else:
            new_inner += '    '
            
        new_block = f"{open_tag}{new_inner}{close_tag}"
        new_content = content[:match.start()] + new_block + content[match.end():]
        target_file.write_text(new_content, encoding='utf-8', newline='\n')
        self.logger.debug(f"Injected {added_count} items into array '{array_name}' ({target_dir.name}/{target_file.name})")
