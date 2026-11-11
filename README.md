# Tiny City

A pixel-art screen saver where civilisation evolves while you're away.

Leave your computer alone and an empty patch of wilderness slowly grows into huts, farms, castles, factories, skyscrapers and, finally, a green future city full of electric cars, drones, solar towers and maglev trains. Move the mouse or press a key to come back. Next time you step away, the city picks up where it left off.

![A metropolis at night](docs/hero.png)

## The eras

| | |
|:-:|:-:|
| ![Wilderness](docs/0-wilderness.png) **Wilderness**<br>Trees and deer. | ![Stone Age](docs/1-stone-age.png) **Stone Age**<br>The first huts and campfires. |
| ![Farming Village](docs/2-farming-village.png) **Farming Village**<br>Fields, wooden houses, ox carts. | ![Medieval Town](docs/3-medieval-town.png) **Medieval Town**<br>Stone houses, windmills, castle towers. |
| ![Industrial Age](docs/4-industrial-age.png) **Industrial Age**<br>Smokestacks and the first steam train. | ![Modern City](docs/5-modern-city.png) **Modern City**<br>Cars, apartment blocks, street lights. |
| ![Metropolis](docs/6-metropolis.png) **Metropolis**<br>Skyscrapers, buses, planes. | ![Green Future](docs/7-green-future.png) **Green Future**<br>Vertical forests, drones, maglev trains. |

The city also has a day and night cycle, with sunsets, stars, lit windows, smog that comes with industry and clears again later, boats on the river and traffic that changes with each era.

## Install on Windows

You need [Python 3](https://www.python.org/downloads/) to build it once. After that, the screen saver runs without Python.

```
git clone https://github.com/derrickbarasa/evolution.git
cd evolution
py -m venv .venv
.venv\Scripts\python.exe -m pip install pygame pyinstaller
.venv\Scripts\python.exe -m PyInstaller --noconfirm TinyCity.spec
copy dist\TinyCity.exe dist\TinyCity.scr
```

Then right-click `dist\TinyCity.scr`, choose **Install**, set how many idle minutes to wait, and click **OK**.

To pick how long each era lasts, click **Settings** in the screen saver dialog. The same window shows how far your city has grown and has a button to start a new one.

## Run it directly

Tiny City also runs as a normal program, on Windows, macOS or Linux, with `pip install pygame`:

```
python tiny_city.py                 start now, full screen
python tiny_city.py --window        windowed test mode (Esc quits, Right arrow skips an era)
python tiny_city.py --fast          every era lasts 15 seconds (demo)
python tiny_city.py --watch         sit in the background, start after 5 idle minutes
python tiny_city.py --watch --idle-minutes 10 --era-minutes 5
python tiny_city.py --new           forget the saved city and start from wilderness
python tiny_city.py --settings      open the settings window
```

`--watch` reads the system idle time. On Linux it needs `xprintidle` (`sudo apt install xprintidle`).

## Where things are saved

- The city: `%APPDATA%\TinyCity\city.sav` (`~/TinyCity/city.sav` on macOS and Linux). It's saved every 30 seconds and when you come back.
- Settings: `settings.json` in the same folder.

A save made on a screen with a very different shape, such as an ultrawide monitor, is ignored and a new city starts, so the layout never looks stretched.
