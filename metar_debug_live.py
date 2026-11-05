"""프로젝트 루트에서 실행: python metar_debug_live.py
METAR API를 한 번 호출해 XML 원본 요소와 정규화 결과를 비교합니다. DB 쓰기 없음.
"""
import json
from collections import Counter
from xml.etree import ElementTree as ET

from collection.pipeline.sources import load_sources
from collection.pipeline.collector import fetch
from collection.pipeline.metar_parser import extract_metar_items, parse_metar, local_name, get_measure

FIELDS = {'wind_gust_mps': 'windGustSpeed', 'visibility_km': 'prevailingVisibility', 'weather_phenomena': 'presentWeather'}


def main():
    source = load_sources()['metar']
    print('METAR API 원본 조회 중 (DB 저장 없음)...')
    body, status, content_type = fetch(source, mode='live')
    print('HTTP:', status, 'Content-Type:', content_type)
    data = json.loads(body)
    items = extract_metar_items(data)
    print('응답 항목 수:', len(items))
    if not items:
        print('항목 없음. 응답 최상위 키:', list(data) if isinstance(data, dict) else type(data).__name__)
        return

    stats = {key: Counter() for key in FIELDS}
    examples = {key: [] for key in FIELDS}
    parse_errors = []
    for i, item in enumerate(items):
        xml_text = item.get('metarMsg')
        if not isinstance(xml_text, str) or not xml_text.strip():
            parse_errors.append((i, 'metarMsg 없음'))
            continue
        try:
            root = ET.fromstring(xml_text)
            normalized = parse_metar(item)
        except Exception as exc:
            parse_errors.append((i, f'{type(exc).__name__}: {exc}'))
            continue
        for key, tag in FIELDS.items():
            nodes = [el for el in root.iter() if local_name(el.tag) == tag]
            present = bool(nodes)
            result = normalized.get(key)
            stats[key]['원본 요소 존재' if present else '원본 요소 없음'] += 1
            stats[key]['정규화 값 존재' if result is not None else '정규화 NULL'] += 1
            if present and result is None:
                stats[key]['원본 존재하지만 NULL'] += 1
                if len(examples[key]) < 5:
                    examples[key].append({
                        'record_index': i,
                        'nodes': [{'text': (el.text or '').strip()[:100], 'attributes': el.attrib} for el in nodes[:3]],
                        'measure': get_measure(root, tag) if key != 'weather_phenomena' else None,
                    })
    for key in FIELDS:
        print('\n===', key, '===')
        for k, v in stats[key].items():
            print(f'{k}: {v}')
        if examples[key]:
            print('원본에는 있으나 NULL인 사례:')
            print(json.dumps(examples[key], ensure_ascii=False, indent=2))
    if parse_errors:
        print('\n파싱 오류:', len(parse_errors))
        for error in parse_errors[:5]: print(error)
    print('\n진단 완료: API 1회 조회, DB 변경 없음')


if __name__ == '__main__':
    main()
