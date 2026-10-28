"""Build local browser QA bundles; --fixtures uses explicitly synthetic test data.

Run from the repository root: python scripts/build_webos_qa_bundles.py /tmp/lg-qa --fixtures
Nothing is installed on a TV. The destination must not contain existing bundles.
"""
import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.cleanyourtv_themes import CleanyourtvThemes
from core.webos_home import build_bundle
from core import vn_calendar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--fixtures', action='store_true')
    args = parser.parse_args()
    data = {}
    if args.fixtures:
        data = {
            'generated': 'QA fixture (synthetic, not live)',
            'weather': {'city': 'Hà Nội', 'temp': 28, 'text': 'Có mây',
                        'humidity': 70, 'aqi': 50, 'high': 30, 'low': 24,
                        'forecast': [{'label': 'Thứ Hai', 'high': 30, 'low': 24}] * 5},
            'lunar': vn_calendar.lunar_card(date(2026, 10, 28), 2),
            'gold': {'items': [{'name': 'Vàng SJC', 'buy': 100000000, 'sell': 102000000}] * 3},
            'fuel': {'items': [{'name': 'RON95', 'price': 20000}] * 3},
        }
    apps = [{'id': 'netflix', 'title': 'Netflix'},
            {'id': 'youtube.leanback.v4', 'title': 'YouTube'}]
    args.destination.mkdir(parents=True, exist_ok=True)
    for theme in CleanyourtvThemes().list_themes():
        build_bundle(theme, args.destination / theme['config']['design_profile'],
                     apps=apps, widget_data=data)


if __name__ == '__main__':
    main()
