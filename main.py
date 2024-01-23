"""
Given a Google Drive/Dropbox link to a PDF, it will download the PDF,
compress the PDF, and upload it to DocumentCloud.
"""
import os
import sys
import shutil
import subprocess
from documentcloud.addon import AddOn
from clouddl import grab


class Compress(AddOn):
    """Downloads the file, runs Ghostscript to compress the file,
    and uploads to DocumentCloud if file is <500MB"""

    def check_permissions(self):
        """The user must be a verified journalist to upload a document"""
        self.set_message("Checking permissions...")
        user = self.client.users.get("me")
        if not user.verified_journalist: #pylint: disable=no-member
            self.set_message(
                "You need to be verified to use this add-on. Please verify your "
                "account here: https://airtable.com/shrZrgdmuOwW0ZLPM"
            )
            sys.exit()

    def fetch_files(self, url):
        """Fetch the files from either a cloud share link or any public URL"""
        self.set_message("Retrieving files to compress...")
        os.makedirs(os.path.dirname("./out/"), exist_ok=True)
        grab(url, "./out/")
        filenames = os.listdir("./out/")
        os.chdir("./out/")
        for file in filenames:
            os.rename(file, file.replace(" ", "-"))
        os.chdir("..")

    def compress_pdf(self, file_path, no_ext):
        """Uses ghostscript to compress the PDF"""
        # pylint:disable = line-too-long
        bash_cmd = f"gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 -dPDFSETTINGS=/screen -dNOPAUSE -dQUIET -dBATCH -sOutputFile={no_ext}-compressed.pdf {file_path};"
        subprocess.call(bash_cmd, shell=True)

    def main(self):
        """The main add-on functionality goes here."""
        # pylint:disable=too-many-locals
        url = self.data.get("url")
        access_level = self.data["access_level"]
        project_id = self.data.get("project_id")
        if project_id is not None:
            kwargs = {"project": project_id}
        else:
            kwargs = {}
        self.check_permissions()
        self.fetch_files(url)
        successes = 0
        errors = 0
        for current_path, _folders, files in os.walk("./out/"):
            for file_name in files:
                file_name = os.path.join(current_path, file_name)
                self.set_message("Attempting to compress PDF files")
                abs_path = os.path.abspath(file_name)
                file_name_no_ext = os.path.splitext(abs_path)[0]
                try:
                    self.compress_pdf(abs_path, file_name_no_ext)
                except RuntimeError as runtime_error:
                    self.send_mail(
                        "Runtime Error for Compression AddOn",
                        "Please forward this to info@documentcloud.org \n"
                        + str(runtime_error),
                    )
                    errors += 1
                    continue
                else:
                    file_stat = os.stat(f"{file_name_no_ext}-compressed.pdf")
                    if file_stat.st_size > 525336576:
                        self.set_message(
                            f"Your file {file_name_no_ext}-compressed.pdf is too big to upload. "
                            "Try splitting up the file before uploading"
                        )
                        errors += 1
                    else:
                        self.set_message(
                            "Uploading compressed file to DocumentCloud..."
                        )
                        self.client.documents.upload(
                            f"{file_name_no_ext}-compressed.pdf",
                            access=access_level,
                            **kwargs,
                        )
                        successes += 1
        sfiles = "file" if successes == 1 else "files"
        efiles = "file" if errors == 1 else "files"
        self.set_message(f"Compressed {successes} {sfiles}, skipped {errors} {efiles}")
        shutil.rmtree("./out", ignore_errors=False, onerror=None)


if __name__ == "__main__":
    Compress().main()
