
# import os
import json
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.core.window import Window
from yt_dlp import YoutubeDL
import requests

Window.size = (900, 650)

def search_youtube(query, limit=8):
    results = []
    ydl_opts = {'quiet': True, 'extract_flat': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        for e in info.get('entries', []):
            results.append({'title': e.get('title', 'Без названия'), 'url': e.get('webpage_url', '')})
    return results

def download_audio(url, title):
    filename = f"{title[:40].replace('/', '_').replace(' ', '_')}.mp3"
    if os.path.exists(filename):
        return filename
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'quiet': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return filename if os.path.exists(filename) else None

def get_lyrics(song_title):
    try:
        r = requests.get(f"https://api.lyrics.ovh/v1/{song_title.replace(' ', '%20')}", timeout=5)
        if r.status_code == 200:
            return r.json().get('lyrics', 'Текст не найден')[:2000]
    except:
        pass
    return "Текст не найден"

class Playlist:
    def __init__(self, name):
        self.name = name
        self.songs = []
    def to_dict(self):
        return {'name': self.name, 'songs': self.songs}
    @staticmethod
    def from_dict(d):
        p = Playlist(d['name'])
        p.songs = d['songs']
        return p

class SwillifyApp(App):
    def build(self):
        self.playlists = []
        self.current_playlist = None
        self.current_song_index = 0
        self.current_sound = None
        self.load_data()

        main = BoxLayout(orientation='vertical', padding=10, spacing=10)
        top = BoxLayout(size_hint=(1, 0.08))
        for name, callback in [('📀 Плейлисты', self.show_playlists), ('🔍 Поиск', self.show_search), ('📝 Текст', self.show_lyrics)]:
            btn = Button(text=name)
            btn.bind(on_press=callback)
            top.add_widget(btn)
        main.add_widget(top)

        self.content = BoxLayout(orientation='vertical', size_hint=(1, 0.7))
        main.add_widget(self.content)

        player = BoxLayout(size_hint=(1, 0.1), spacing=10)
        self.now_label = Label(text='🎵 Нет трека')
        for text, cb in [('⏪', self.prev_song), ('▶', self.play_current), ('⏸', self.pause_music), ('⏹', self.stop_music), ('⏩', self.next_song)]:
            btn = Button(text=text)
            btn.bind(on_press=cb)
            player.add_widget(btn)
        player.add_widget(self.now_label)
        main.add_widget(player)

        self.status = Label(text='✅ Готов', size_hint=(1, 0.05))
        main.add_widget(self.status)

        self.show_playlists(None)
        return main

    def show_playlists(self, _):
        self.content.clear_widgets()
        layout = BoxLayout(orientation='vertical')
        new_box = BoxLayout(size_hint=(1, 0.1))
        self.pl_name_input = TextInput(hint_text='Название плейлиста')
        btn_create = Button(text='✨ Создать')
        btn_create.bind(on_press=self.create_playlist)
        new_box.add_widget(self.pl_name_input)
        new_box.add_widget(btn_create)
        layout.add_widget(new_box)

        scroll = ScrollView()
        self.pl_list = GridLayout(cols=1, size_hint_y=None, spacing=5)
        self.pl_list.bind(minimum_height=self.pl_list.setter('height'))
        scroll.add_widget(self.pl_list)
        layout.add_widget(scroll)
        self.content.add_widget(layout)
        self.refresh_playlists()

    def show_search(self, _):
        self.content.clear_widgets()
        layout = BoxLayout(orientation='vertical', spacing=10)
        self.search_input = TextInput(hint_text='🔍 Название песни')
        btn_search = Button(text='Найти')
        btn_search.bind(on_press=self.do_search)
        layout.add_widget(self.search_input)
        layout.add_widget(btn_search)
        scroll = ScrollView()
        self.search_results = GridLayout(cols=1, size_hint_y=None, spacing=5)
        self.search_results.bind(minimum_height=self.search_results.setter('height'))
        scroll.add_widget(self.search_results)
        layout.add_widget(scroll)
        self.content.add_widget(layout)

    def show_lyrics(self, _):
        self.content.clear_widgets()
        layout = BoxLayout(orientation='vertical')
        self.lyrics_title = Label(text='Текст текущей песни', size_hint=(1, 0.1))
        scroll = ScrollView()
        self.lyrics_text = Label(text='Выберите песню', size_hint_y=None, valign='top')
        self.lyrics_text.bind(size=self.lyrics_text.setter('text_size'))
        scroll.add_widget(self.lyrics_text)
        layout.add_widget(self.lyrics_title)
        layout.add_widget(scroll)
        self.content.add_widget(layout)

    def refresh_playlists(self):
        self.pl_list.clear_widgets()
        for idx, pl in enumerate(self.playlists):
            box = BoxLayout(size_hint_y=None, height=60, spacing=10)
            label = Label(text=f'{pl.name} [{len(pl.songs)}]', size_hint=(0.6, 1))
            btn_open = Button(text='🎵', size_hint=(0.2, 1))
            btn_del = Button(text='🗑', size_hint=(0.2, 1))
            btn_open.bind(on_press=lambda x, i=idx: self.open_playlist(i))
            btn_del.bind(on_press=lambda x, i=idx: self.delete_playlist(i))
            box.add_widget(label)
            box.add_widget(btn_open)
            box.add_widget(btn_del)
            self.pl_list.add_widget(box)

    def create_playlist(self, _):
        name = self.pl_name_input.text.strip()
        if name:
            self.playlists.append(Playlist(name))
            self.save_data()
            self.refresh_playlists()
            self.pl_name_input.text = ''

    def delete_playlist(self, idx):
        self.playlists.pop(idx)
        self.save_data()
        self.refresh_playlists()

    def open_playlist(self, idx):
        pl = self.playlists[idx]
        self.current_playlist = pl
        content = BoxLayout(orientation='vertical')
        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
        grid.bind(minimum_height=grid.setter('height'))
        for i, s in enumerate(pl.songs):
            row = BoxLayout(size_hint_y=None, height=50, spacing=10)
            row.add_widget(Label(text=f'{i+1}. {s["title"][:40]}', size_hint=(0.6, 1)))
            btn_play = Button(text='▶', size_hint=(0.2, 1))
            btn_play.bind(on_press=lambda x, idx=i: self.play_from_playlist(idx))
            row.add_widget(btn_play)
            grid.add_widget(row)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        popup = Popup(title=pl.name, content=content, size_hint=(0.9, 0.8))
        popup.open()

    def play_from_playlist(self, idx):
        if self.current_playlist and idx < len(self.current_playlist.songs):
            self.current_song_index = idx
            self.play_song(self.current_playlist.songs[idx])

    def do_search(self, _):
        query = self.search_input.text.strip()
        if not query:
            return
        self.status.text = '🔍 Поиск...'
        threading.Thread(target=self._search_thread, args=(query,)).start()

    def _search_thread(self, query):
        results = search_youtube(query)
        Clock.schedule_once(lambda dt: self._show_results(results), 0)

    def _show_results(self, results):
        self.search_results.clear_widgets()
        for r in results:
            row = BoxLayout(size_hint_y=None, height=50, spacing=10)
            row.add_widget(Label(text=r['title'][:50], size_hint=(0.7, 1)))
            btn = Button(text='⬇ Скачать', size_hint=(0.3, 1))
            btn.bind(on_press=lambda x, url=r['url'], title=r['title']: self.download_song(url, title))
            row.add_widget(btn)
            self.search_results.add_widget(row)
        self.status.text = f'✅ Найдено {len(results)}'

    def download_song(self, url, title):
        self.status.text = f'⬇ Скачиваю {title}...'
        threading.Thread(target=self._download_thread, args=(url, title)).start()

    def _download_thread(self, url, title):
        path = download_audio(url, title)
        Clock.schedule_once(lambda dt: self._on_downloaded(title, path), 0)

    def _on_downloaded(self, title, path):
        if path and os.path.exists(path):
            self.status.text = f'✅ Скачано: {title}'
            self.ask_add_to_playlist(title, path)
        else:
            self.status.text = '❌ Ошибка скачивания'

    def ask_add_to_playlist(self, title, path):
        content = BoxLayout(orientation='vertical', spacing=10)
        content.add_widget(Label(text=f'"{title}" скачана'))
        scroll = ScrollView(size_hint=(1, 0.6))
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
        grid.bind(minimum_height=grid.setter('height'))
        for pl in self.playlists:
            btn = Button(text=pl.name, size_hint_y=None, height=40)
            btn.bind(on_press=lambda x, p=pl: self.add_to_playlist(p, title, path, popup))
            grid.add_widget(btn)
        scroll.add_widget(grid)
        content.add_widget(scroll)
        popup = Popup(title='Добавить в плейлист', content=content, size_hint=(0.8, 0.7))
        popup.open()

    def add_to_playlist(self, pl, title, path, popup):
        pl.songs.append({'title': title, 'path': path})
        self.save_data()
        popup.dismiss()
        self.status.text = f'✅ "{title}" добавлен в {pl.name}'

    def play_song(self, song):
        if self.current_sound:
            self.current_sound.stop()
        self.current_sound = SoundLoader.load(song['path'])
        if self.current_sound:
            self.current_sound.play()
            self.now_label.text = f'🎵 {song["title"][:40]}'
            threading.Thread(target=self._load_lyrics, args=(song['title'],)).start()

    def _load_lyrics(self, title):
        lyrics = get_lyrics(title)
        Clock.schedule_once(lambda dt: self._update_lyrics_ui(title, lyrics), 0)

    def _update_lyrics_ui(self, title, lyrics):
        self.lyrics_title.text = f'📝 {title[:60]}'
        self.lyrics_text.text = lyrics

    def play_current(self, _):
        if self.current_sound:
            self.current_sound.play()

    def pause_music(self, _):
        if self.current_sound:
            self.current_sound.stop()

    def stop_music(self, _):
        if self.current_sound:
            self.current_sound.stop()
            self.current_sound = None
            self.now_label.text = '🎵 Нет трека'

    def next_song(self, _):
        if self.current_playlist and self.current_playlist.songs:
            self.current_song_index = (self.current_song_index + 1) % len(self.current_playlist.songs)
            self.play_song(self.current_playlist.songs[self.current_song_index])

    def prev_song(self, _):
        if self.current_playlist and self.current_playlist.songs:
            self.current_song_index = (self.current_song_index - 1) % len(self.current_playlist.songs)
            self.play_song(self.current_playlist.songs[self.current_song_index])

    def save_data(self):
        with open('playlists.json', 'w') as f:
            json.dump([p.to_dict() for p in self.playlists], f)

    def load_data(self):
        if os.path.exists('playlists.json'):
            with open('playlists.json', 'r') as f:
                data = json.load(f)
                self.playlists = [Playlist.from_dict(d) for d in data]

if __name__ == '__main__':
    SwillifyApp().run()
print("Hello")
