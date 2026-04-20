'''
Copyright © 2026 ppekko

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

import os
import sys
import subprocess
import re

VERSION = "3.1"

def check_dependencies(force=False):
    all_deps = ['pytz', 'markdown', 'watchdog']
    missing = []
    for d in all_deps:
        try: __import__(d)
        except ImportError: missing.append(d)
    
    if not missing and not force:
        return

    print("\n" + "="*50)
    print("  PMMS DEPENDENCY CHECK")
    print("="*50)
    print(f"missing packages: {', '.join(missing) if missing else '[none]'}")
    print("\nplease choose an option:")
    print("1. exit and install packages manually" + (f" (pip install {' '.join(missing)})" if missing else ""))
    print("2. install via pip now" + (" (only missing)" if missing else " (nothing to install)"))
    print("3. setup a virtual environment (venv) and create run.py now\n\n")
    print("if you are using an externally managed environment (such as arch linux), select 3")
    
    choice = input("\nchoice [1-3]: ").strip()
    
    if choice == '1':
        sys.exit(0)
    elif choice == '2':
        if not missing:
            print("nothing to install.")
            return
        print(f"\ninstalling {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        print("\ninstallation complete. please restart pmms.")
        sys.exit(0)
    elif choice == '3':
        print("\nsetting up venv...")
        subprocess.check_call([sys.executable, "-m", "venv", ".venv"])
        
        print(f"installing all required packages into venv: {', '.join(all_deps)}")
        venv_pip = os.path.join(".venv", "bin", "pip") if os.name != 'nt' else os.path.join(".venv", "Scripts", "pip")
        subprocess.check_call([venv_pip, "install"] + all_deps)
        
        # create run.py
        with open("run.py", "w") as f:
            f.write(f"""import os
import sys
import subprocess

venv_python = os.path.join(".venv", "bin", "python") if os.name != 'nt' else os.path.join(".venv", "Scripts", "python")
if not os.path.exists(venv_python):
    print("error: virtual environment not found. please run pmms.py --setup")
    sys.exit(1)

subprocess.call([venv_python, "pmms.py"] + sys.argv[1:])
""")
        print("\nvirtual environment created and dependencies installed.\n")
        print("\n" + "="*50)
        print("created 'run.py'. you can now use 'python3 run.py' to run pmms via the venv.")
        print("="*50)
        sys.exit(0)
    else:
        print("invalid choice. exiting.")
        sys.exit(1)

if __name__ == "__main__":
    force_setup = '--setup' in sys.argv
    skip_deps = '--skip-deps' in sys.argv
    
    if force_setup:
        if '--setup' in sys.argv: sys.argv.remove('--setup')
        check_dependencies(force=True)
    elif not skip_deps:
        check_dependencies()
    elif skip_deps:
        sys.argv.remove('--skip-deps')

import shutil
import threading
import time
import termios
import contextlib
import configparser
import pytz
import markdown
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(msg, color=Colors.ENDC):
    now = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.OKCYAN}[{now}]{Colors.ENDC} {color}{msg}{Colors.ENDC}")

def print_success(msg): log(msg, Colors.OKGREEN)
def print_info(msg): log(msg, Colors.OKBLUE)
def print_warning(msg): log(msg, Colors.WARNING)
def print_error(msg): log(msg, Colors.FAIL)
def print_header(msg): print(f"\n{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")

class SiteGenerator:
    def __init__(self, src_dir):
        self.src_dir = os.path.abspath(src_dir)
        self.dst_dir = os.path.join(self.src_dir, '_output')
        self.layout_dir = os.path.join(self.src_dir, '_layout')
        self.blacklist_file = os.path.join(self.src_dir, 'blacklist.txt')
        self.blacklist = self._load_blacklist()
        self.processed_dirs = set()
        self._dir_config_cache = {}

    def _load_dir_config(self, dir_path):
        abs_dir = os.path.abspath(dir_path)
        if abs_dir in self._dir_config_cache:
            return self._dir_config_cache[abs_dir]
            
        config_path = os.path.join(abs_dir, 'pmms.config')
        meta = {}
        if os.path.exists(config_path):
            config = configparser.ConfigParser()
            try:
                with open(config_path, 'r') as f:
                    config.read_string('[blog]\n' + f.read())
                meta = dict(config.items('blog'))
            except Exception as e:
                print_error(f"error reading config {config_path}: {e}")
        
        self._dir_config_cache[abs_dir] = meta
        return meta

    def _get_merged_meta(self, path):
        # normalize to absolute path of the directory
        current = os.path.abspath(path if os.path.isdir(path) else os.path.dirname(path))
        
        all_meta = {}
        # collect configs from bottom up to root
        configs = []
        while current.startswith(self.src_dir):
            meta = self._load_dir_config(current)
            if meta:
                configs.append(meta)
            if current == self.src_dir:
                break
            current = os.path.dirname(current)
            
        # merge
        for meta in reversed(configs):
            all_meta.update(meta)
        return all_meta

    def _load_blacklist(self):
        if not os.path.exists(self.blacklist_file):
            return []
        with open(self.blacklist_file, 'r') as f:
            raw = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return [os.path.abspath(os.path.join(self.src_dir, b)) for b in raw]

    def is_blacklisted(self, path):
        if not os.path.isabs(path):
            abs_path = os.path.normpath(os.path.join(self.src_dir, path))
        else:
            abs_path = os.path.normpath(path)
            
        for b in self.blacklist:
            if abs_path == b or abs_path.startswith(f"{b}{os.sep}"):
                return True
        return False

    def get_creation_date(self, path):
        try:
            timestamp = os.path.getctime(path)
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return "unknown date"

    def _parse_html_meta(self, content):
        meta = {}
        cleaned_content = content
        # look for <!-- layout: ... --> or similar
        match = re.search(r'^\s*<!--\s*(.*?)\s*-->', content, re.DOTALL)
        if match:
            meta_block = match.group(1)
            # parse "key: value"
            for line in meta_block.split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    meta[key.strip().lower()] = val.strip()
            # remove the comment block from content
            cleaned_content = content[match.end():].lstrip()
        return meta, cleaned_content

    def apply_layout(self, content, layout_path=None, meta=None, extra_meta=None):
        if not meta: meta = {}
        
        # combine meta and extra_meta
        combined_meta = extra_meta.copy() if extra_meta else {}
        for k, v in meta.items():
            combined_meta[k] = v
            
        # determine layout content
        layout_content = "{{content}}"
        potential_layouts = []
        if layout_path: potential_layouts.append(layout_path)
        potential_layouts.append(os.path.join(self.layout_dir, 'index.html'))

        for lp in potential_layouts:
            if os.path.exists(lp):
                try:
                    with open(lp, 'r') as f:
                        layout_content = f.read()
                    break
                except Exception as e:
                    print_error(f"error reading layout {lp}: {e}")

        # replace placeholders
        final_html = layout_content
        if '{{content}}' in final_html:
            final_html = final_html.replace('{{content}}', content)
        else:
            final_html += content

        # inject metadata
        for key, values in combined_meta.items():
            val = values[0] if isinstance(values, list) else values
            final_html = final_html.replace(f'{{{{meta_{key}}}}}', str(val))

        # system placeholders
        final_html = final_html.replace('_PMMSVER_', VERSION)
        return final_html

    def process_markdown(self, src_path, layout_path=None, extra_meta=None):
        try:
            md = markdown.Markdown(extensions=['fenced_code', 'tables', 'toc', 'meta'])
            with open(src_path, 'r') as f:
                content = f.read()
            
            html_body = md.convert(content)
            meta = md.Meta if hasattr(md, 'Meta') else {}
            
            # metadata layout override
            if 'layout' in meta:
                override_name = meta['layout'][0]
                override_path = os.path.join(self.layout_dir, override_name)
                if os.path.exists(override_path):
                    layout_path = override_path

            final_html = self.apply_layout(html_body, layout_path, meta, extra_meta)
            date = self.get_creation_date(src_path)
            final_html = final_html.replace('_PMMSGENDATE_', date)
            
            return final_html, meta, date
        except Exception as e:
            print_error(f"error processing markdown {src_path}: {e}")
            return None, None, None

    def process_blog(self, blog_src_dir, blog_dst_dir):
        blog_meta = self._load_dir_config(blog_src_dir)
        if not blog_meta: return

        posts_dir_name = blog_meta.get('posts_dir', 'posts')
        layout_name = blog_meta.get('layout')
        index_layout_name = blog_meta.get('index_layout')
        index_filename = blog_meta.get('index_filename', 'index.html')
        generate_index = str(blog_meta.get('generate_index', 'true')).lower() == 'true'
        generate_blog = str(blog_meta.get('generate_blog', 'true')).lower() == 'true'
        
        if not generate_blog: return

        src_posts_dir = os.path.join(blog_src_dir, posts_dir_name)
        if not os.path.exists(src_posts_dir): return

        layout_path = os.path.join(self.layout_dir, layout_name) if layout_name else None
        
        posts_data = []
        for root, _, files in os.walk(src_posts_dir):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, src_posts_dir)
                dst_file = os.path.join(blog_dst_dir, rel_path)
                
                rel_file_to_src = os.path.relpath(src_file, self.src_dir)
                if self.is_blacklisted(rel_file_to_src):
                    print_info(f"blacklisted: {file}")
                    self.copy_item(src_file, dst_file)
                    continue
                
                if file.endswith('.md'):
                    dst_html = os.path.splitext(dst_file)[0] + '.html'
                    html, meta, date = self.process_markdown(src_file, layout_path, blog_meta)
                    if html:
                        os.makedirs(os.path.dirname(dst_html), exist_ok=True)
                        with open(dst_html, 'w') as f: f.write(html)
                        title = meta.get('title', [file])[0]
                        posts_data.append({'title': title, 'link': os.path.relpath(dst_html, blog_dst_dir), 'date': date})
                        print_success(f"blog post: {rel_path} -> {os.path.basename(dst_html)}")
                else:
                    self.copy_item(src_file, dst_file)
        
        # generate index
        if generate_index and index_layout_name:
            idx_layout_path = os.path.join(self.layout_dir, index_layout_name)
            if os.path.exists(idx_layout_path):
                posts_data.sort(key=lambda x: x['date'], reverse=True)
                list_html = '<ul class="blog-list">\n'
                for p in posts_data:
                    list_html += f'  <li><span class="post-date">{p["date"]}</span> - <a href="{p["link"]}">{p["title"]}</a></li>\n'
                list_html += '</ul>'
                
                final_idx = self.apply_layout(list_html, idx_layout_path, blog_meta)

                final_idx = final_idx.replace('{{post_list}}', list_html)
                final_idx = final_idx.replace('_PMMSGENDATE_', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
                with open(os.path.join(blog_dst_dir, index_filename), 'w') as f: f.write(final_idx)
                print_success(f"blog index generated: {index_filename}")

    def copy_item(self, src, dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    def clean(self):
        if os.path.exists(self.dst_dir):
            shutil.rmtree(self.dst_dir)
            print_warning("cleaned _output directory.")

    def build(self):
        self.clean()
        os.makedirs(self.dst_dir, exist_ok=True)
        self.processed_dirs.clear()

        # process blogs
        for root, dirs, files in os.walk(self.src_dir):
            if 'pmms.config' in files:
                config = self._load_dir_config(root)
                posts_dir = config.get('posts_dir', 'posts')
                generate_blog = str(config.get('generate_blog', 'true')).lower() == 'true'
                
                if generate_blog and os.path.exists(os.path.join(root, posts_dir)):
                    rel = os.path.relpath(root, self.src_dir)
                    if rel == '.': continue
                    dst_blog_dir = os.path.join(self.dst_dir, rel)
                    if not self.is_blacklisted(os.path.relpath(root, self.src_dir)):
                        self.process_blog(root, dst_blog_dir)
                        self.processed_dirs.add(root)

        # copy and process remaining files
        for root, dirs, files in os.walk(self.src_dir):
            if any(root.startswith(p) for p in self.processed_dirs): continue
            if '_output' in root or '.git' in root or '_layout' in root: continue
            
            rel_root = os.path.relpath(root, self.src_dir)
            dst_root = os.path.join(self.dst_dir, rel_root if rel_root != '.' else '')
            
            for file in files:
                if file == 'pmms.py' or file == 'blacklist.txt' or file.startswith(('.', '_')): continue
                src_file = os.path.join(root, file)
                dst_file = os.path.join(dst_root, file)
                
                rel_file = os.path.relpath(src_file, self.src_dir)
                if self.is_blacklisted(rel_file):
                    print_info(f"blacklisted: {file}")
                    self.copy_item(src_file, dst_file)
                    continue
                
                if file.endswith('.md'):
                    dst_html = os.path.splitext(dst_file)[0] + '.html'
                    extra_meta = self._get_merged_meta(src_file)
                    html, _, _ = self.process_markdown(src_file, extra_meta=extra_meta)
                    if html:
                        os.makedirs(os.path.dirname(dst_html), exist_ok=True)
                        with open(dst_html, 'w') as f: f.write(html)
                        print_success(f"converted: {file}")
                elif file.endswith('.html'):
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    with open(src_file, 'r') as f: content = f.read()
                    
                    # preprocess for dates/version
                    content = content.replace('_PMMSVER_', VERSION)
                    content = content.replace('_PMMSGENDATE_', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
                    # apply layout if not a full doc
                    marker_found = any(m in content.lower() for m in ['<!doctype', '<html', '<body'])
                    if not marker_found:
                        meta, cleaned_content = self._parse_html_meta(content)
                        layout_path = None
                        if 'layout' in meta:
                            override_name = meta['layout']
                            override_path = os.path.join(self.layout_dir, override_name)
                            if os.path.exists(override_path):
                                layout_path = override_path
                        
                        extra_meta = self._get_merged_meta(src_file)
                        content = self.apply_layout(cleaned_content, layout_path, meta, extra_meta)
                    
                    with open(dst_file, 'w') as f: f.write(content)
                    print_success(f"processed: {file}")
                else:
                    self.copy_item(src_file, dst_file)

        self.generate_robots_txt()

    def build_incremental(self, src_path):
        src_path = os.path.abspath(src_path)
        
        # check if in blog
        current = os.path.dirname(src_path)
        blog_dir = None
        while current and current != self.src_dir and current.startswith(self.src_dir):
            if os.path.exists(os.path.join(current, 'pmms.config')):
                blog_dir = current
                break
            current = os.path.dirname(current)
            
        if blog_dir:
            rel = os.path.relpath(blog_dir, self.src_dir)
            dst_blog_dir = os.path.join(self.dst_dir, rel)
            if not self.is_blacklisted(os.path.relpath(blog_dir, self.src_dir)):
                self.process_blog(blog_dir, dst_blog_dir)
            return

        if src_path.startswith(os.path.join(self.src_dir, '_output')) or \
           src_path.startswith(os.path.join(self.src_dir, '.git')) or \
           src_path.startswith(os.path.join(self.src_dir, '_layout')):
            return
            
        file = os.path.basename(src_path)
        if file == 'pmms.py' or file == 'blacklist.txt' or file.startswith(('.', '_')):
            return
            
        rel_file = os.path.relpath(src_path, self.src_dir)
        dst_file = os.path.join(self.dst_dir, rel_file)
        
        if self.is_blacklisted(rel_file):
            print_info(f"blacklisted: {file}")
            self.copy_item(src_path, dst_file)
            return
            
        if file.endswith('.md'):
            dst_html = os.path.splitext(dst_file)[0] + '.html'
            extra_meta = self._get_merged_meta(src_path)
            html, _, _ = self.process_markdown(src_path, extra_meta=extra_meta)
            if html:
                os.makedirs(os.path.dirname(dst_html), exist_ok=True)
                with open(dst_html, 'w') as f: f.write(html)
                print_success(f"converted: {file}")
        elif file.endswith('.html'):
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            with open(src_path, 'r') as f: content = f.read()
            
            content = content.replace('_PMMSVER_', VERSION)
            content = content.replace('_PMMSGENDATE_', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            marker_found = any(m in content.lower() for m in ['<!doctype', '<html', '<body'])
            if not marker_found:
                meta, cleaned_content = self._parse_html_meta(content)
                layout_path = None
                if 'layout' in meta:
                    override_name = meta['layout']
                    override_path = os.path.join(self.layout_dir, override_name)
                    if os.path.exists(override_path):
                        layout_path = override_path
                
                extra_meta = self._get_merged_meta(src_path)
                content = self.apply_layout(cleaned_content, layout_path, meta, extra_meta)
            
            with open(dst_file, 'w') as f: f.write(content)
            print_success(f"processed: {file}")
        else:
            self.copy_item(src_path, dst_file)

    def generate_robots_txt(self):
        if not self.blacklist: return
        path = os.path.join(self.dst_dir, 'robots.txt')
        with open(path, 'w') as f:
            f.write("user-agent: *\n")
            for b in self.blacklist:
                f.write(f"disallow: /{os.path.relpath(b, self.src_dir)}/\n")
        print_success("robots.txt generated.")

class StyledRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        code = args[1]
        color = Colors.OKGREEN if code.startswith('2') else Colors.OKBLUE if code.startswith('3') else Colors.FAIL
        log(f"{format % args}", color)

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            try:
                with open('404.html', 'rb') as f:
                    content = f.read()
                self.send_response(404)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            except:
                pass
        super().send_error(code, message, explain)

def run_server(target_dir):
    os.chdir(target_dir)
    TCPServer.allow_reuse_address = True
    try:
        with TCPServer(("", 8000), StyledRequestHandler) as httpd:
            print_header("serving at http://localhost:8000")
            print_info("press 'p' to exit.")
            httpd.serve_forever()
    except Exception as e:
        print_error(f"server error: {e}")

@contextlib.contextmanager
def raw_mode(file):
    old_attrs = termios.tcgetattr(file.fileno())
    new_attrs = old_attrs[:]
    new_attrs[3] &= ~(termios.ECHO | termios.ICANON)
    try:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
        yield
    finally:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, generator):
        self.generator = generator
        self.last_run = 0

    def handle_event(self, event):
        if event.is_directory or '_output' in event.src_path: return
        if time.time() - self.last_run < 1: return # debounce
        
        rel_path = os.path.relpath(event.src_path, self.generator.src_dir)
        full_rebuild_triggers = ['_layout', 'pmms.config', 'blacklist.txt', 'pmms.py', 'run.py']
        if any(rel_path.startswith(t) for t in full_rebuild_triggers):
            print_warning(f"structural change detected: {rel_path}. full rebuild...")
            self.generator.build()
        else:
            print_info(f"change detected: {os.path.basename(event.src_path)}")
            self.generator.build_incremental(event.src_path)
            
        self.last_run = time.time()

    def on_modified(self, event): self.handle_event(event)
    def on_created(self, event): self.handle_event(event)

def main():
    # startup banner
    banner = f"""
░█▀█░█▀█▀█░█▀█▀█░█▀▀░    please make my site ({VERSION})
░█▀▀░█░█░█░█░█░█░▀▀█░    github.com/ppekko
░▀░░░▀░▀░▀░▀░▀░▀░▀▀▀░
"""
    print(f"{Colors.HEADER}{Colors.BOLD}\n{banner.strip()}{Colors.ENDC}\n")
    
    gen = SiteGenerator(os.getcwd())
    print_info(f"source: {gen.src_dir}")
    print_info(f"target: {gen.dst_dir}")
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'clean': gen.clean()
        elif cmd == 'gen': gen.build()
        elif cmd == 'pub':
            if len(sys.argv) < 3:
                print_error("error: 'pub' requires a service argument (e.g., 'pmms.py pub surge')")
                return
            service = sys.argv[2]
            gen.build()
            if service == "surge":
                print_info(f"publishing to surge...")
                subprocess.run([service], cwd=gen.dst_dir)
        return

    gen.build()
    
    observer = Observer()
    observer.schedule(FileChangeHandler(gen), gen.src_dir, recursive=True)
    observer.start()
    
    server_thread = threading.Thread(target=run_server, args=(gen.dst_dir,), daemon=True)
    server_thread.start()

    try:
        with raw_mode(sys.stdin):
            while True:
                if sys.stdin.read(1).lower() == 'p':
                    print_header("exiting...")
                    break
    except KeyboardInterrupt:
        print_header("\ninterrupted")
    finally:
        observer.stop()
        observer.join()
        gen.clean()

if __name__ == "__main__":
    main()
