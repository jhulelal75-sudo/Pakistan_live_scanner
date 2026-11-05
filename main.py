

import socket
import ssl
import csv
import os
import time
import threading
import urllib.request
import urllib.error
from queue import Queue

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView


SUBDOMAINS = [
    "www", "mail", "api", "portal", "mobile",
    "app", "cdn", "static", "support", "vpn",
    "webmail", "status", "test", "dev"
]

NETWORKS = [
    "Jazz",
    "Zong",
    "Ufone",
    "Telenor",
    "SCOM"
]


class PakistanScanner(App):

    def build(self):
        self.title = "Pakistan Live Scanner"
        self.results = []
        self.queue = Queue()
        self.running = False

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8)
        )

        title = Label(
            text="[b]PAKISTAN TELECOM LIVE SCANNER[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(55),
            font_size="19sp"
        )
        root.add_widget(title)

        self.network = Spinner(
            text="Select Network",
            values=NETWORKS,
            size_hint_y=None,
            height=dp(48)
        )
        root.add_widget(self.network)

        self.domain = TextInput(
            hint_text="Enter authorized domain e.g. example.com",
            multiline=False,
            size_hint_y=None,
            height=dp(48)
        )
        root.add_widget(self.domain)

        self.subdomains = TextInput(
            text="\n".join(SUBDOMAINS),
            hint_text="One subdomain per line",
            size_hint_y=None,
            height=dp(115)
        )
        root.add_widget(self.subdomains)

        buttons = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(6)
        )

        start = Button(
            text="START",
            background_color=(0.05, 0.55, 0.25, 1)
        )
        start.bind(on_press=self.start_scan)

        stop = Button(
            text="STOP",
            background_color=(0.75, 0.15, 0.15, 1)
        )
        stop.bind(on_press=self.stop_scan)

        export = Button(text="EXPORT CSV")
        export.bind(on_press=self.export_csv)

        buttons.add_widget(start)
        buttons.add_widget(stop)
        buttons.add_widget(export)
        root.add_widget(buttons)

        self.status = Label(
            text="Ready",
            size_hint_y=None,
            height=dp(35)
        )
        root.add_widget(self.status)

        self.scroll = ScrollView()

        self.output = Label(
            text="Scan results will appear here.",
            size_hint_y=None,
            halign="left",
            valign="top"
        )
        self.output.bind(
            texture_size=self.update_output_height
        )

        self.scroll.add_widget(self.output)
        root.add_widget(self.scroll)

        Clock.schedule_interval(self.process_queue, 0.2)

        return root

    def update_output_height(self, instance, size):
        instance.height = size[1] + dp(20)
        instance.text_size = (self.scroll.width - dp(20), None)

    def start_scan(self, instance):

        if self.running:
            return

        domain = self.domain.text.strip().lower()

        if (
            not domain
            or len(domain) > 253
            or "/" in domain
            or ":" in domain
            or " " in domain
        ):
            self.status.text = "Enter a valid domain"
            return

        if self.network.text not in NETWORKS:
            self.status.text = "Select a network"
            return

        labels = [
            x.strip().lower()
            for x in self.subdomains.text.splitlines()
            if x.strip()
        ]

        if len(labels) > 50:
            self.status.text = "Maximum 50 subdomains"
            return

        if any(
            not x.replace("-", "").isalnum()
            for x in labels
        ):
            self.status.text = "Invalid subdomain label"
            return

        self.results = []
        self.output.text = ""
        self.running = True
        self.status.text = "Scanning..."

        hosts = [domain]

        for label in labels:
            hosts.append(label + "." + domain)

        threading.Thread(
            target=self.worker,
            args=(hosts,),
            daemon=True
        ).start()

    def worker(self, hosts):

        for host in hosts:

            if not self.running:
                break

            result = self.check_host(host)

            self.queue.put(result)

        self.queue.put(("DONE", "", "", ""))

    def check_host(self, host):

        ip = "DNS FAILED"
        http = "NO RESPONSE"
        elapsed = "-"

        try:
            ip = socket.gethostbyname(host)
        except OSError:
            return (host, ip, http, elapsed)

        for scheme in ["https", "http"]:

            try:
                start = time.time()

                request = urllib.request.Request(
                    scheme + "://" + host,
                    headers={
                        "User-Agent": "Pakistan-Live-Scanner/1.0"
                    },
                    method="GET"
                )

                context = ssl.create_default_context()

                with urllib.request.urlopen(
                    request,
                    timeout=5,
                    context=context
                ) as response:

                    http = str(response.status)

                elapsed = str(
                    round((time.time() - start) * 1000)
                ) + " ms"

                break

            except urllib.error.HTTPError as error:

                http = str(error.code)
                break

            except Exception:
                continue

        return (host, ip, http, elapsed)

    def process_queue(self, dt):

        while not self.queue.empty():

            result = self.queue.get()

            if result[0] == "DONE":

                self.running = False
                self.status.text = (
                    "Completed: " + str(len(self.results))
                    + " hosts"
                )
                continue

            self.results.append(result)

            host, ip, http, elapsed = result

            line = (
                f"{host}\n"
                f"IP: {ip} | HTTP: {http} | {elapsed}\n"
                "----------------------------\n"
            )

            self.output.text += line

            self.status.text = (
                "Checked: " + str(len(self.results))
            )

    def stop_scan(self, instance):

        self.running = False
        self.status.text = "Stopping..."

    def export_csv(self, instance):

        if not self.results:
            self.status.text = "No results to export"
            return

        path = os.path.join(
            self.user_data_dir,
            "pakistan_scanner_results.csv"
        )

        try:

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(file)

                writer.writerow([
                    "Host",
                    "IP Address",
                    "HTTP Status",
                    "Response Time"
                ])

                writer.writerows(self.results)

            self.status.text = "CSV saved: " + path

        except Exception as error:
            self.status.text = "Export error: " + str(error)


if __name__ == "__main__":
    PakistanScanner().run()
      
