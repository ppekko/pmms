```
░█▀█░█▀█▀█░█▀█▀█░█▀▀░    please make my site
░█▀▀░█░█░█░█░█░█░▀▀█░    github.com/ppekko
░▀░░░▀░▀░▀░▀░▀░▀░▀▀▀░
```

# please make my site

pmms is a small but powerful static site generator, enclosed within a 600~ LOC python file. Like jekyll but with none of the fuss.
(unix only, windows will not like it because no termios)

## features

- **zero configuration required**: simply download, make your layout and run.
- **standardized layouts**: uses a single `_layout/index.html` file as a layout for your entire site (unless specified otherwise) (use this for menu bars and the like).
- **markdown to html**: automatically converts `.md` files to `.html` pages.
- **development server**: built-in http server with auto-reload (watchdog).
- **automated blog**: recursive post discovery, automatic index generation, and date-based sorting.
- **metadata injection**: easy way to add and inject data into your pages
- **deployment ready**: integrated surge.sh support (with more to come potentially).
- **dependency management**: built-in interactive installer for required packages.

## installation and usage

simply download `pmms.py` and run it using python:

```bash
wget https://raw.githubusercontent.com/ppekko/pmms/main/pmms.py
python3 pmms.py
```

dependencies are checked on run, and you will be prompted to automatically or manually install them if they are missing (a virtual environment can automatically be set up if needed).

### commands

- `(no command)`: builds the site, starts the dev server at `http://localhost:8000`, and watches for file changes. generated site is deleted when the server is stopped.
- `gen`: builds the site into the `_output/` directory.
- `clean`: deletes the `_output/` directory and all generated files should you manually generate the site.
- `pub`: builds the site and deploys it to a specified provider (given below, place provider name after `pub`)
    - `surge`: deploys to [surge.sh](https://surge.sh)

### flags

- `--setup`: force the dependency check/installer menu to show up.
- `--skip-deps`: skip the dependency check entirely.

## site structure

- `_layout/`: put your `index.html` here. use `{{content}}` where you want your page content to go.
- `_output/`: output directory (do not touch). gets automatically deleted (and manually with `clean`).
- `blacklist.txt`: list files or folders (one per line) that pmms should ignore.
- `pmms.config`: used in blog subdirectories to configure post locations and index generation.

## configuration & blogs

To configure a directory (for metadata or blog settings), add a `pmms.config` file to the folder.

### global & scoped configuration
- **Root `pmms.config`**: Settings apply to your entire site.
- **Subdirectory `pmms.config`**: Settings applies to that folder and its descendants, overriding root values.

### blog settings
To enable blog features for a folder, add these to its `pmms.config`:
```ini
posts_dir = posts        # where your .md posts are (relative to config)
layout = blog_post.html  # layout for posts (in _layout/)
index_layout = index.html # layout for the blog index page
index_filename = index.html
generate_index = true    # disable to skip index generation
generate_blog = true     # set to false to use config only for metadata
```

pmms will recursively find all markdown files in the `posts_dir`, convert them, and generate a chronological list on the blog's index page.

## layouts

Layouts are stored in the `_layout/` directory. By default, `pmms` looks for `_layout/index.html`. 

A layout must contain the `{{content}}` placeholder, which is where the page's HTML body will be injected.

## metadata & injection

You can inject dynamic content into your layouts using `{{meta_[key]}}`. `pmms` collects metadata from three sources, merged in this order (1 being highest priority):

1. **File Metadata**: Defined at the top of an individual file.
   - **Markdown**: `title: My Page` at the top of `.md`.
   - **HTML**: Inside a comment at the very top:
     ```html
     <!--
     layout: your_layout.html
     title: Custom Title
     -->
     ```
2. **Scoped Config**: Any key-value pair in a `pmms.config` within the current directory.
3. **Global Config**: Any key-value pair in the root `pmms.config`.

### reserved placeholders
- `{{content}}`: The main body of the page (required in layouts).
- `_PMMSVER_`: The current version of `pmms`.
- `_PMMSGENDATE_`: The date/time the site was generated.
- `{{post_list}}`: A list of blog posts (blog index pages only).

### custom layouts
Specify a custom layout by adding `layout: filename.html` to any metadata source. By default, `pmms` uses `_layout/index.html`.

### blacklist
You can prevent HTML modification (markdown conversion, layouts, placeholder injection) for certain files or directories by listing them in a `blacklist.txt` file in your source root. These files will still be included in the site but will be copied as-is, but will also be added to a generated robots.txt to not be indexed by search engines.

- List one file or directory path per line.
- Relative paths are relative to the project root.
- Lines starting with `#` are treated as comments.

Example `blacklist.txt`:
```text
# ignore draft posts
blog/posts/draft-post.md
# ignore design assets
assets/psd
```

## future plans

Theming? maybe?

## history

pmms began life in early 2024 as at the time I was attempting to use jekyll to generate my personal site. However, I was encountering many issues with ruby and the dependencies that jekyll needed, despite many re-installs (hence the name). So, out of frustration, I decided to write my own simple python script that would stitch a header on top of every html file of my website (at the time that was all that was needed). Over time I would slowly add features, such as blog posts and a local test server. For a long while this project was kept private until I was convinced by some friends to put it out, and so 2-ish years here we are. Enjoy.

# license

Copyright © 2026 ppekko

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
