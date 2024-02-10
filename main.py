from subprocess import DEVNULL, STDOUT, Popen, call
from threading import Thread
from pathlib import Path
from flask import Flask, send_file
from time import sleep
import requests
import re
import sys


class Local2Public:
    def __init__(self, tun_port: int, metric_port: int, dir: Path) -> None:
        self.tun_port = tun_port
        self.metric_port = metric_port
        self.web_app = Flask(__name__)
        self.dir = dir

    def check_bin(self) -> None:
        """Check for cloudflared binary"""

        if (
            call("cloudflared --version", shell=True, stdout=DEVNULL, stderr=DEVNULL)
            != 0
        ):
            print(
                "Cloudflare's Tunnel service is not installed. Please install it before continuing."
            )
            sys.exit(1)

    def start_tunnel(self) -> None:
        """Starts Tunnel and return public url"""

        self.proc = Popen(
            f"cloudflared tunnel --url localhost:{self.tun_port} --metrics localhost:{self.metric_port}".split(
                " "
            ),
            stdout=DEVNULL,
            stderr=STDOUT,
        )

    def set_public_url(self) -> str | None:
        """Sets public url"""

        for _ in range(10):
            try:
                metrics = requests.get(
                    f"http://localhost:{self.metric_port}/metrics"
                ).text
                reg_search = re.search(
                    r"(?P<url>https?[^\s]+.trycloudflare.com)", metrics
                )
                reg = reg_search.group("url") if reg_search else None
                if reg:
                    self.public_url = reg
                    return reg
            except requests.exceptions.ConnectionError:
                sleep(0.5)
        self.proc.kill()
        return None

    def run_flask(self) -> None:
        """Run Flask web server which will serve files"""

        @self.web_app.route("/<file>")
        def _(file: str):
            return send_file(f"{self.dir}/{file}")

        self.flask_thread = Thread(
            target=self.web_app.run, args=("127.0.0.1", self.tun_port)
        )
        self.flask_thread.daemon = True
        self.flask_thread.start()

    def write_file(self) -> None:
        """Writes a links.txt file which will include links of all available files"""

        if not self.public_url:
            raise ValueError("No public_url found")
        with open("links.txt", "w") as file:
            for i in self.dir.iterdir():
                file.write(f"{self.public_url}/{i.name}\n")


if __name__ == "__main__":
    inst = Local2Public(1234, 3214, Path("toupload"))
    inst.check_bin()
    try:
        inst.start_tunnel()
        public_url = inst.set_public_url()
        print(f"[i] Public Url: {public_url}") if public_url else print(
            "Failed to get Public Url"
        )
        inst.run_flask()
        inst.write_file()
        print("[+] File Is Ready!")
    except Exception as e:
        print('Error: ', e)
    finally:
        inst.proc.wait()
