import os
import shutil
import subprocess
import readline
from datetime import datetime
import getpass
from dotenv import load_dotenv

# Enable tab completion
readline.parse_and_bind('tab: complete')

# Constants
GITENV_PATH = os.path.expanduser("~/.Gitenv")
WRITEUPS_PATH = os.path.expanduser("~/writeups")

def setup_tab_completion():
    """Configure tab completion for paths"""
    readline.parse_and_bind('tab: complete')
    readline.set_completer_delims(' \t\n;')
    readline.set_completer(path_completer)

def path_completer(text, state):
    """Enhanced path completer with better directory handling"""
    if "~" in text:
        text = os.path.expanduser(text)
    if os.path.isdir(text) and text.endswith('/'):
        directory = text
        prefix = ''
    else:
        directory = os.path.dirname(text) or '.'
        prefix = os.path.basename(text)
    try:
        names = os.listdir(directory)
        if prefix:
            names = [n for n in names if n.startswith(prefix)]
        dirs = sorted(n for n in names if os.path.isdir(os.path.join(directory, n)))
        files = sorted(n for n in names if os.path.isfile(os.path.join(directory, n)))
        names = dirs + files
        matches = [os.path.join(directory, name) + '/' if os.path.isdir(os.path.join(directory, name)) else os.path.join(directory, name) for name in names]
        return matches[state] if state < len(matches) else None
    except OSError:
        return None

def get_repo_path():
    """Ask for the repository path with tab completion."""
    setup_tab_completion()
    while True:
        repo_path = input("\nEnter the path to the repository (use Tab for completion): ").strip()
        repo_path = os.path.expanduser(repo_path)
        if os.path.isdir(repo_path) and os.path.exists(os.path.join(repo_path, ".git")):
            return repo_path
        print("❌ Invalid repository path. Please provide a valid path containing a .git folder.")

def setup_gitenv():
    """Set up the GitHub token in ~/.Gitenv."""
    if os.path.exists(GITENV_PATH):
        print(f"Using existing GitHub token from {GITENV_PATH}.")
        return
    print("GitHub token not found. Let's set it up.")
    github_token = input("Enter your GitHub token: ").strip()
    with open(GITENV_PATH, "w") as f:
        f.write(f"GITHUB_TOKEN={github_token}")
    print(f"GitHub token saved to {GITENV_PATH}.")

def get_github_token():
    """Retrieve the GitHub token from ~/.Gitenv."""
    if not os.path.exists(GITENV_PATH):
        setup_gitenv()
    load_dotenv(GITENV_PATH)
    return os.getenv("GITHUB_TOKEN")

def ensure_writeups_folder():
    """Ensure the ~/writeups folder exists."""
    if not os.path.exists(WRITEUPS_PATH):
        os.makedirs(WRITEUPS_PATH)
        print(f"Created writeups folder at {WRITEUPS_PATH}.")
    return WRITEUPS_PATH

class WriteupGenerator:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.repo_name = os.path.basename(os.path.normpath(repo_path))
        self.markdown = ""
        self.images = []
        self.title = ""
        self.steps = []  # List of (subtitle, description, oneliner, image_name)
        self.flags = []  # List of flags
        self.entries = []  # Ordered list of all entries: ('title', value), ('image', (name, path)), ('description', index), ('flag', index)

    def show_menu(self):
        print("\n" + "=" * 40)
        print("WRITEUP GENERATOR")
        print("=" * 40)
        print("Current Structure:")
        for i, (type_, value) in enumerate(self.entries, 1):
            if type_ == 'title':
                print(f"{i:>3}. Title: {value}")
            elif type_ == 'image':
                print(f"{i:>3}. Machine Image: {value[1]}")
            elif type_ == 'description':
                subtitle = self.steps[value][0]
                print(f"{i:>3}. Description: {subtitle}")
            elif type_ == 'flag':
                flag = self.flags[value]
                print(f"{i:>3}. Flag: {flag[:4]}****")
        print("\nOptions:")
        options = [
            ("1", "Add Title"),
            ("2", "Add Machine Image"),
            ("3", "Add Description with Subtitle, One-liner, and/or Image"),
            ("4", "Add Flag"),
            ("5", "Edit Steps"),
            ("F", "Finish and Generate Writeup"),
            ("Q", "Quit without Saving")
        ]
        for opt, label in options:
            print(f"{opt:>3}. {label}")
        return input("\nSelect an option: ").upper()

    def add_title(self):
        new_title = input("\nEnter the machine title: ").strip()
        if new_title:
            self.title = new_title
            if ('title', self.title) not in self.entries:
                self.entries.append(('title', self.title))
            self.regenerate_markdown()
            print("✅ Title updated.")
        else:
            print("❌ Title cannot be empty.")

    def add_machine_image(self):
        setup_tab_completion()
        while True:
            image_path = input("\nEnter the path to the machine image (use Tab for completion): ").strip()
            image_path = os.path.expanduser(image_path)
            if os.path.isfile(image_path):
                self.images = [img for img in self.images if img[0] != "machine_image"]
                self.images.append(("machine_image", image_path))
                self.entries = [e for e in self.entries if not (e[0] == 'image' and e[1][0] == "machine_image")]
                self.entries.append(('image', ("machine_image", image_path)))
                self.regenerate_markdown()
                print("✅ Machine image updated.")
                break
            else:
                print("❌ File not found. Please check the path.")

    def process_references(self, text):
        words_to_process = []
        current_text = text
        while '[' in current_text and ']' in current_text:
            start = current_text.find('[')
            end = current_text.find(']')
            word = current_text[start + 1:end]
            if word not in [w for w, _ in words_to_process]:
                words_to_process.append((word, None))
            current_text = current_text[end + 1:]
        if words_to_process:
            print("\nEnter URLs for references:")
            for i, (word, _) in enumerate(words_to_process):
                url = input(f"URL for '{word}': ")
                words_to_process[i] = (word, url)
        result = text
        for word, url in words_to_process:
            result = result.replace(f"[{word}]", f"[{word}]({url})")
        return result

    def add_description(self):
        subtitle = input("\nEnter the subtitle for this section: ").strip()
        print("\nEnter the description (type 'END' on a new line to finish):")
        description = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            line = self.process_references(line)
            description.append(line)

        add_oneliner = input("Add a one-liner? (y/n): ").lower()
        oneliner = None
        if add_oneliner == 'y':
            oneliner = input("Enter the one-liner (terminal style): ").strip()

        add_image = input("Add an image? (y/n): ").lower()
        image_name = None
        if add_image == 'y':
            setup_tab_completion()
            while True:
                image_path = input("Enter the path to the image (Tab for completion): ").strip()
                image_path = os.path.expanduser(image_path)
                if os.path.isfile(image_path):
                    image_name = input("Enter a name for the image (e.g., 'scan_results'): ").strip() or f"image_{len(self.images)}"
                    self.images.append((image_name, image_path))
                    break
                else:
                    print("❌ File not found. Please check the path.")

        self.steps.append((subtitle, description, oneliner, image_name))
        self.entries.append(('description', len(self.steps) - 1))
        self.regenerate_markdown()
        print("✅ Description added.")

    def add_flag(self):
        print("\nEnter the flag (it will be partially hidden in the markdown):")
        real_flag = input().strip()
        if not real_flag:
            print("❌ Flag cannot be empty.")
            return
        print(f"\nFlag entered: {real_flag}")
        if input("\nConfirm adding this flag? (y/n): ").lower() == 'y':
            self.flags.append(real_flag)
            self.entries.append(('flag', len(self.flags) - 1))
            self.regenerate_markdown()
            print("✅ Flag added successfully.")
        else:
            print("❌ Flag addition cancelled.")

    def edit_steps(self):
        if not self.entries:
            print("No steps to edit.")
            return

        while True:
            print("\nEdit Steps:")
            print("=" * 40)
            for i, (type_, value) in enumerate(self.entries, 1):
                if type_ == 'title':
                    print(f"{i:>3}. Title: {value}")
                elif type_ == 'image':
                    print(f"{i:>3}. Machine Image: {value[1]}")
                elif type_ == 'description':
                    subtitle = self.steps[value][0]
                    print(f"{i:>3}. Description: {subtitle}")
                elif type_ == 'flag':
                    flag = self.flags[value]
                    print(f"{i:>3}. Flag: {flag[:4]}****")
            print("  b. Go back")

            choice = input("\nSelect an option: ").lower()
            if choice == 'b':
                break

            if choice.isdigit():
                choice = int(choice) - 1
                if 0 <= choice < len(self.entries):
                    type_, value = self.entries[choice]
                    if type_ == 'title':
                        self.add_title()
                    elif type_ == 'image':
                        self.add_machine_image()
                    elif type_ == 'description':
                        self.edit_description(value)
                    elif type_ == 'flag':
                        self.edit_flag(value)
                    self.regenerate_markdown()
                else:
                    print("❌ Invalid option. Try again.")
            else:
                print("❌ Invalid option. Try again.")

    def get_image_path(self, image_name):
        return next((path for name, path in self.images if name == image_name), "None")

    def edit_description(self, index):
        while True:
            subtitle, description, oneliner, image_name = self.steps[index]
            print(f"\nEditing Description: {subtitle}")
            print("=" * 40)
            print(f"1. Edit Subtitle: {subtitle}")
            print(f"2. Edit Description: {' '.join(description[:1])}...")
            print(f"3. Edit One-liner: {oneliner if oneliner else 'None'}")
            print(f"4. Edit Image: {self.get_image_path(image_name) if image_name else 'None'}")
            print("b. Go back")

            choice = input("\nSelect what to edit: ").lower()
            if choice == 'b':
                break

            if choice == '1':
                new_subtitle = input(f"New subtitle (current: '{subtitle}'): ").strip() or subtitle
                self.steps[index] = (new_subtitle, description, oneliner, image_name)
                print("✅ Subtitle updated.")

            elif choice == '2':
                print(f"\nCurrent description:\n{' '.join(description)}")
                print("\nEnter new description (type 'END' on a new line to finish, leave blank to keep current):")
                new_description = []
                while True:
                    line = input()
                    if line.strip().upper() == 'END':
                        break
                    new_description.append(self.process_references(line))
                self.steps[index] = (subtitle, new_description or description, oneliner, image_name)
                print("✅ Description updated.")

            elif choice == '3':
                new_oneliner = input(f"New one-liner (current: '{oneliner if oneliner else 'None'}', press Enter to keep): ").strip()
                self.steps[index] = (subtitle, description, new_oneliner if new_oneliner else oneliner, image_name)
                print("✅ One-liner updated.")

            elif choice == '4':
                current_image_path = self.get_image_path(image_name) if image_name else "None"
                print(f"Current image: {current_image_path}")
                add_image = input("Change image? (y/n): ").lower()
                if add_image == 'y':
                    setup_tab_completion()
                    image_path = input("Enter new image path (Tab for completion): ").strip()
                    if image_path and os.path.isfile(os.path.expanduser(image_path)):
                        new_image_name = input("Enter new image name (press Enter to keep current): ").strip() or image_name or f"image_{len(self.images)}"
                        self.images = [img for img in self.images if img[0] != image_name]
                        self.images.append((new_image_name, os.path.expanduser(image_path)))
                        self.steps[index] = (subtitle, description, oneliner, new_image_name)
                        print("✅ Image updated.")
                    else:
                        print("❌ Invalid image path.")
                elif add_image == 'n' and image_name:
                    print("Image unchanged.")
                else:
                    self.steps[index] = (subtitle, description, oneliner, None)
                    self.images = [img for img in self.images if img[0] != image_name]
                    print("✅ Image removed.")
            self.regenerate_markdown()

    def edit_flag(self, index):
        while True:
            flag = self.flags[index]
            print(f"\nEditing Flag: {flag[:4]}****")
            print("=" * 40)
            print(f"1. Edit Flag: {flag[:4]}****")
            print("b. Go back")

            choice = input("\nSelect what to edit: ").lower()
            if choice == 'b':
                break

            if choice == '1':
                new_flag = input(f"New flag (current: '{flag}'): ").strip()
                if new_flag:
                    self.flags[index] = new_flag
                    print("✅ Flag updated.")
                    self.regenerate_markdown()
                else:
                    print("❌ Flag cannot be empty.")

    def regenerate_markdown(self):
        self.markdown = f"# {self.title}\n\n" if self.title else ""
        for img_name, _ in self.images:
            if img_name == "machine_image":
                self.markdown += f"<div align='center'>\n  <img src='machine_image.png' width='400' alt='Machine Image'>\n</div>\n\n"
        for subtitle, description, oneliner, image_name in self.steps:
            self.markdown += f"## {subtitle}\n\n"
            self.markdown += "\n".join(description) + "\n\n"
            if oneliner:
                self.markdown += f"```bash\n{oneliner}\n```\n\n"
            if image_name:
                self.markdown += f"<div align='center'>\n  <img src='{image_name}.png' width='600' alt='{subtitle}'>\n</div>\n\n"
        if self.flags:
            self.markdown += "\n## Flags\n\n"
            for flag in self.flags:
                flag_length = len(flag)
                blurred = flag[:flag_length // 2] + "*" * (flag_length - flag_length // 2)
                self.markdown += f"```bash\n{blurred}\n```\n"

    def add_footer(self):
        self.markdown += "\n## Siguenos\n\n"
        self.markdown += "<div align='center'>\n"
        self.markdown += "  <p>Thanks for reading! Follow me on my socials:</p>\n"
        self.markdown += "  <a href='https://x.com/@imahian'><img src='https://www.vectorlogo.zone/logos/x/x-icon.svg' alt='X' width='40'></a>\n"
        self.markdown += "  <a href='https://discord.gg/dbesG8EX'><img src='https://www.vectorlogo.zone/logos/discord/discord-icon.svg' alt='Discord' width='40'></a>\n"
        self.markdown += "  <a href='https://youtube.com/@imahian'><img src='https://www.vectorlogo.zone/logos/youtube/youtube-icon.svg' alt='YouTube' width='40'></a>\n"
        self.markdown += "  <a href='https://twitch.tv/imahian'><img src='https://www.vectorlogo.zone/logos/twitch/twitch-icon.svg' alt='Twitch' width='40'></a>\n"
        self.markdown += "</div>\n\n"
        self.markdown += "---\n"

    def generate_writeup(self):
        self.regenerate_markdown()
        self.add_footer()
        if not self.title:
            print("\n⚠️ No title provided, using default filename.")
            filename = "untitled_writeup.md"
        else:
            filename = f"{self.title.replace(' ', '_').lower()}.md"
        writeups_folder = ensure_writeups_folder()
        file_path = os.path.join(writeups_folder, filename)
        with open(file_path, 'w') as f:
            f.write(self.markdown)
        print(f"\n✅ Writeup generated successfully: {file_path}")
        return file_path

def recursive_folder_selection(base_path):
    while True:
        print("\nAvailable folders:")
        folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]
        for i, folder in enumerate(folders, 1):
            print(f"{i}. {folder}")
        print(f"{len(folders) + 1}. Select this folder")
        print(f"{len(folders) + 2}. Go back")
        choice = input("Enter the number of the folder to navigate (or 's' to select this folder, 'b' to go back): ")
        if choice.lower() == 's':
            return base_path
        if choice.lower() == 'b':
            return None
        try:
            choice = int(choice) - 1
            if choice < 0 or choice >= len(folders) + 2:
                print("❌ Invalid choice.")
                continue
            if choice == len(folders):
                return base_path
            if choice == len(folders) + 1:
                return None
            selected_folder = folders[choice]
            new_path = os.path.join(base_path, selected_folder)
            result = recursive_folder_selection(new_path)
            if result:
                return result
        except ValueError:
            print("❌ Invalid input. Please enter a number.")

def get_target_folder(repo_path):
    print("\nSelect the folder to save the writeup:")
    target_folder = recursive_folder_selection(repo_path)
    if not target_folder:
        print("❌ No folder selected.")
        return None
    return target_folder

def upload_to_github(file_path, images, target_folder):
    machine_folder = os.path.join(target_folder, os.path.splitext(os.path.basename(file_path))[0])
    os.makedirs(machine_folder, exist_ok=True)
    shutil.copy(file_path, os.path.join(machine_folder, os.path.basename(file_path)))
    for image_name, image_path in images:
        new_image_name = f"{image_name}.png"
        shutil.copy(image_path, os.path.join(machine_folder, new_image_name))
    os.chdir(target_folder)
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Add writeup: {os.path.basename(machine_folder)}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"\n✅ Writeup and images uploaded to GitHub in folder: {os.path.basename(machine_folder)}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing Git commands: {e}")

def main():
    print("""
    .------------------------------------------------------------------------------.
    |                             .mmMMMMMMMMMMMMMmm.                              |
    |                         .mMMMMMMMMMMMMMMMMMMMMMMMm.                          |
    |                      .mMMMMMMMMMMMMMMMMMMMMMMMMMMMMMm.                       |
    |                    .MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.                     |
    |                  .MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.                   |
    |                 MMMMMMMM'  `"MMMMM~~~~~~~MMMM""`  'MMMMMMMM                  |
    |                MMMMMMMMM                           MMMMMMMMM                 |
    |               MMMMMMMMMM:                         :MMMMMMMMMM                |
    |              .MMMMMMMMMM                           MMMMMMMMMM.               |
    |              MMMMMMMMM"                             "MMMMMMMMM               |
    |              MMMMMMMMM                               MMMMMMMMM               |
    |              MMMMMMMMM           REPWRITER           MMMMMMMMM               |
    |              MMMMMMMMMM                             MMMMMMMMMM               |
    |              `MMMMMMMMMM                           MMMMMMMMMM`               |
    |               MMMMMMMMMMMM.                     .MMMMMMMMMMMM                |
    |                MMMMMM  MMMMMMMMMM         MMMMMMMMMMMMMMMMMM                 |
    |                 MMMMMM  'MMMMMMM           MMMMMMMMMMMMMMMM                  |
    |                  `MMMMMM  "MMMMM           MMMMMMMMMMMMMM`                   |
    |                    `MMMMMm                 MMMMMMMMMMMM`                     |
    |                      `"MMMMMMMMM           MMMMMMMMM"`                       |
    |                         `"MMMMMM           MMMMMM"`                          |
    |                             `""M           M""`                              |
    '------------------------------------------------------------------------------'
    """)

    try:
        github_token = get_github_token()
        repo_path = get_repo_path()
        generator = WriteupGenerator(repo_path)

        while True:
            choice = generator.show_menu()
            if choice == '1':
                generator.add_title()
            elif choice == '2':
                generator.add_machine_image()
            elif choice == '3':
                generator.add_description()
            elif choice == '4':
                generator.add_flag()
            elif choice == '5':
                generator.edit_steps()
            elif choice == 'F':
                md_file = generator.generate_writeup()
                if md_file:
                    target_folder = get_target_folder(repo_path)
                    if target_folder and os.path.exists(target_folder):
                        upload_to_github(md_file, generator.images, target_folder)
                    else:
                        print(f"❌ Target folder not found or not selected.")
                break
            elif choice == 'Q':
                print("\n❌ Operation canceled")
                break
            else:
                print("\n⚠️ Invalid option, try again")

    except KeyboardInterrupt:
        print("\n❌ Operation canceled (Ctrl+C pressed)")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    main()
