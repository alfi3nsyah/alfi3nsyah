import math
import os
import struct
import threading
import time
import wave
from datetime import datetime
from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
import requests

URL_AUTOGEMPA = "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json"
URL_TERKINI = "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json"
URL_DIRASAKAN = "https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.json"
URL_CUACA = (
    "https://api.open-meteo.com/v1/forecast?"
    "latitude=-6.9175&longitude=107.6191&current=temperature_2m,weather_code,precipitation&timezone=Asia%2FJakarta"
)

FILE_TSUNAMI = "sirine_tsunami.wav"
MY_LAT = -6.5500
MY_LON = 106.7000


def hitung_radius(lat1, lon1, lat2=MY_LAT, lon2=MY_LON):
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2) + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * (math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(r * c)


def generate_tsunami_siren():
    if os.path.exists(FILE_TSUNAMI):
        return
    sample_rate = 16000
    cycle_duration = 2.5
    cycles = 2
    f_min = 380.0
    f_max = 720.0
    total_samples = int(sample_rate * cycle_duration * cycles)

    try:
        with wave.open(FILE_TSUNAMI, "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            phase = 0.0
            for i in range(total_samples):
                t = i / sample_rate
                cycle_pos = (t % cycle_duration) / cycle_duration
                current_freq = f_min + (f_max - f_min) * (
                    0.5 * (1 - math.cos(2 * math.pi * cycle_pos))
                )
                phase += 2 * math.pi * current_freq / sample_rate
                val = int(32767.0 * 0.9 * math.sin(phase))
                wav.writeframesraw(struct.pack("<h", val))
    except Exception:
        pass


def is_target_zone(lat, lon, wilayah):
    w = wilayah.lower()
    keywords = [
        "jabar",
        "jawa barat",
        "banten",
        "selat sunda",
        "sumur",
        "sukabumi",
        "cianjur",
        "garut",
        "tasikmalaya",
        "pangandaran",
        "bandung",
        "bogor",
        "lebak",
        "pandeglang",
        "sumedang",
        "kuningan",
        "majalengka",
        "subang",
        "purwakarta",
        "bekasi",
        "karawang",
        "cirebon",
        "ciamis",
        "banjar",
        "pelabuhanratu",
        "bayah",
        "ujung kulon",
        "muarabinuangeun",
        "panimbang",
        "laut selatan jawa",
        "selatan jawa",
        "kepseribu",
        "jakarta",
    ]
    if any(k in w for k in keywords):
        return True
    return -8.8 <= lat <= -5.5 and 105.0 <= lon <= 109.2


class SeismicSentinelApp(App):
    def build(self):
        generate_tsunami_siren()
        self.last_id = None
        self.weather_info = "21.6°C | Cerah Berawan"
        self.countdown = 10

        layout = BoxLayout(orientation="vertical", padding=15)
        self.terminal_label = Label(
            text="Menginisialisasi Radar...",
            font_size="13sp",
            font_name="RobotoMono-Regular"
            if os.path.exists("RobotoMono-Regular.ttf")
            else "Roboto",
            halign="left",
            valign="top",
            markup=True,
        )
        self.terminal_label.bind(size=self.terminal_label.setter("text_size"))
        layout.add_widget(self.terminal_label)

        threading.Thread(target=self.worker_thread, daemon=True).start()
        Clock.schedule_interval(self.update_ui_timer, 1.0)
        return layout

    def play_sound(self):
        try:
            sound = SoundLoader.load(FILE_TSUNAMI)
            if sound:
                sound.volume = 1.0
                sound.play()
        except Exception:
            pass

    def worker_thread(self):
        while True:
            self.fetch_data()
            self.countdown = 10
            for _ in range(10):
                time.sleep(1)
                self.countdown -= 1

    def fetch_data(self):
        try:
            r = requests.get(URL_CUACA, timeout=3)
            if r.status_code == 200:
                cur = r.json().get("current", {})
                temp = cur.get("temperature_2m", "--")
                self.weather_info = f"{temp}°C | Pantau Aktif"
        except Exception:
            pass

        candidates = []
        for url in [URL_DIRASAKAN, URL_TERKINI, URL_AUTOGEMPA]:
            
            try:
                res = requests.get(url, timeout=3)
                if res.status_code == 200:
                    data = res.json().get("Infogempa", {}).get("gempa", [])
                    if isinstance(data, dict):
                        candidates.append(data)
                    else:
                        candidates.extend(data)
            except Exception:
                pass

        matched_quake = None
        for d in candidates:
            wilayah = d.get("Wilayah", "")
            raw_coords = d.get("Coordinates", "")
            lat, lon = 0.0, 0.0
            if raw_coords and "," in raw_coords:
                p = raw_coords.split(",")
                lat, lon = float(p[0].strip()), float(p[1].strip())
            if is_target_zone(lat, lon, wilayah):
                try:
                    mag = float(str(d.get("Magnitude", "0")).replace(",", "."))
                    if 1.1 <= mag <= 7.9:
                        matched_quake = {
                            "mag": mag,
                            "wilayah": wilayah,
                            "waktu": d.get("DateTime") or f"{d.get('Tanggal', '')} | {d.get('Jam', '')}".strip(" | "),
                            
                            "kedalaman": d.get("Kedalaman", "-"),
                            "lat": lat,
                            "lon": lon,
                        }
                        break
                except ValueError:
                    continue

        self.quake_data = matched_quake
        if matched_quake:
            cid = f"{matched_quake['waktu']}_{matched_quake['mag']}"
            if self.last_id and self.last_id != cid:
                self.play_sound()
            self.last_id = cid

    def update_ui_timer(self, dt):
        now_wib = datetime.now().strftime("%H:%M:%S WIB")
        txt = (
            "[color=00ffff]┌── [color=ffff00]⚡ ALFIANSYAH | WEST JAVA & SUNDA STRAIT ⚡[/color]\n"
            "│[/color] [color=888888]Sektor   :[/color] [color=ffff00]Jabar, Selat Sunda, Sumur Banten[/color]\n"
            "[color=00ffff]│[/color] [color=888888]Filter   :[/color] [color=ff00ff]Skala 1.1 - 7.9 SR (Sensitif)[/color]\n"
            f"[color=00ffff]│[/color] [color=888888]Cuaca    :[/color] [color=00ff00]{self.weather_info}[/color]\n"
            "[color=00ffff]└──[/color]\n\n"
            " [color=ffffff]Status Jaringan :[/color] [color=00ff00]● ONLINE [BMKG][/color]\n"
            f" [color=ffffff]Waktu Pantau    :[/color] [color=00ffff]{now_wib}[/color]\n\n"
            "[color=00ffff]┌── [ TELEMETRI GEMPA ]\n"
        )
        if hasattr(self, "quake_data") and self.quake_data:
            q = self.quake_data
            dist = hitung_radius(q["lat"], q["lon"])
            txt += (
                f"│ [color=ffffff]Waktu     :[/color] {q['waktu']}\n"
                f"│ [color=ffffff]Magnitudo :[/color] [color=ff3333]{q['mag']} SR[/color]\n"
                f"│ [color=ffffff]Kedalaman :[/color] {q['kedalaman']}\n"
                f"│ [color=ffffff]Koordinat :[/color] Lat {q['lat']}° | Lon {q['lon']}°\n"
                f"│ [color=ffffff]Episentrum:[/color] {q['wilayah']}\n"
                f"│ [color=ffffff]Radius    :[/color] [color=00ff00]{dist} KM dari posisi HP[/color]\n"
            )
        else:
            txt += "│ [color=00ff00]Zona maritim dan darat terpantau aman.[/color]\n"
        txt += (
            "[color=00ffff]└──[/color]\n\n"
            f"[color=00ff00]▶ RADAR AKTIF[/color] Memindai sensor... [{self.countdown:2d}s]"
        )
        self.terminal_label.text = txt


if __name__ == "__main__":
    SeismicSentinelApp().run()
  
