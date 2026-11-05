"""Read-only METAR XML diagnostic for collection/normalized_output/metar_raw.json.
Run from repository root: python metar_debug.py
Optional: python metar_debug.py path/to/metar_raw.json
"""
import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET


def load_parser(repo):
    path = repo / 'collection' / 'pipeline' / 'metar_parser.py'
    if not path.exists():
        raise FileNotFoundError(f'파서 파일이 없습니다: {path}')
    spec = importlib.util.spec_from_file_location('project_metar_parser', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def describe(node):
    if node is None:
        return '(요소 없음)'
    text = (node.text or '').strip()
    return f'text={text!r}, attrs={node.attrib}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input', nargs='?', default='collection/normalized_output/metar_raw.json')
    args = ap.parse_args()
    repo = Path.cwd()
    parser = load_parser(repo)
    source = Path(args.input)
    if not source.exists():
        raise FileNotFoundError(f'원본 파일이 없습니다: {source.resolve()}')
    data = json.loads(source.read_text(encoding='utf-8'))
    items = parser.extract_metar_items(data)
    if not items:
        raise ValueError('METAR 항목을 찾지 못했습니다. 원본 JSON 구조를 확인하세요.')
    fields = {
        'wind_gust_mps': ('windGustSpeed', lambda value, unit: parser.to_mps(value, unit)),
        'visibility_km': ('prevailingVisibility', lambda value, unit: parser.to_km(value, unit)),
        'weather_phenomena': ('presentWeather', None),
    }
    counters = {key: Counter() for key in fields}
    examples = {key: [] for key in fields}
    parsed_errors = []
    print(f'원본 파일: {source.resolve()}')
    print(f'METAR 항목: {len(items)}건')
    for index, item in enumerate(items, 1):
        xml = item.get('metarMsg')
        if not isinstance(xml, str) or not xml.strip():
            parsed_errors.append((index, 'metarMsg 없음'))
            continue
        try:
            root = ET.fromstring(xml)
            result = parser.parse_metar(item)
        except (ET.ParseError, ValueError, TypeError) as exc:
            parsed_errors.append((index, str(exc)))
            continue
        for key, (tag, converter) in fields.items():
            elements = [e for e in root.iter() if parser.local_name(e.tag) == tag]
            node = elements[0] if elements else None
            stat = counters[key]
            if not elements:
                stat['element_missing'] += 1
            else:
                stat['element_present'] += 1
            if key == 'weather_phenomena':
                has_raw = any(e.attrib.get('code') or e.attrib.get('{http://www.w3.org/1999/xlink}href') or (e.text or '').strip() for e in elements)
                stat['raw_value_present' if has_raw else 'raw_value_missing'] += 1
            else:
                value, unit = parser.get_measure(root, tag)
                if value is None:
                    stat['raw_numeric_missing'] += 1
                else:
                    stat['raw_numeric_present'] += 1
                    stat[f'unit:{unit!r}'] += 1
                    if converter(value, unit) is None:
                        stat['conversion_failed'] += 1
            if result.get(key) is None:
                stat['normalized_null'] += 1
                if len(examples[key]) < 5:
                    examples[key].append((index, describe(node)))
            else:
                stat['normalized_present'] += 1
    for key, stats in counters.items():
        print(f'\n=== {key} ===')
        for name, count in sorted(stats.items()):
            print(f'  {name}: {count}')
        print('  NULL 예시 (최대 5건):')
        for index, description in examples[key]:
            print(f'    #{index}: {description}')
    print(f'\n파싱 오류: {len(parsed_errors)}건')
    for index, error in parsed_errors[:10]:
        print(f'  #{index}: {error}')
    print('\n해석: element_missing=원본에 요소 없음, conversion_failed=원본 숫자는 있지만 현재 단위 변환 불가')
    print('주의: 이 결과는 현재 입력 파일에 대해서만 유효하며 DB의 과거 140건 전체와 같지 않을 수 있습니다.')

if __name__ == '__main__':
    main()
