# YOLO v6 모델 학습 환경 및 데이터 출처

## 모델 개요

v6는 사람(person)과 손가락 총(finger_gun)을 탐지하는 YOLO11n 기반 2클래스 모델이다. 사전학습 YOLO11n으로 학습한 v3의 best.pt에서 미세조정했으며, v3 사람 데이터는 그대로 유지하고 손동작 데이터를 확대했다.

Open Images V7은 초기 모델과 v2에서 사용했다. v3에서 사람 데이터를 COCO 2017로 교체했으므로 v6의 사람 학습 데이터 출처는 COCO 2017이다. v7에서 추가한 직접 촬영 영상 및 사람+손 합성 장면은 v6에 포함되지 않는다.

## 학습 환경 및 설정

실제 v6 실행 로그(run_v6.log)와 학습 설정(runs/person_finger_gun_v6/args.yaml)을 기준으로 작성했다.

| 항목 | 내용 |
| --- | --- |
| 운영체제 | Windows, Python 가상환경 .venv |
| GPU | NVIDIA GeForce GTX 1660, VRAM 6GB |
| Python | 3.11.9 |
| PyTorch | 2.7.1+cu126 |
| Ultralytics | 8.4.210 |
| 기반 모델 | YOLO11n, 시작 가중치는 v3 best.pt |
| 클래스 | 0: person / 1: finger_gun |
| 입력 크기 | 640 × 640 |
| 배치 크기 | 4 |
| Optimizer | AdamW |
| 초기 학습률 | 0.0002 |
| Weight decay | 0.0005 |
| 최대 학습 횟수 | 40 epoch |
| 조기 종료 | patience 12, 29 epoch에서 종료 |
| 최고 체크포인트 | 17 epoch |
| 학습 시간 | 약 44분(results.csv 누적 2,620초 기준) |
| 기타 | GPU 0, workers 2, AMP 비활성화, cache 비활성화, seed 0 |
| 주요 증강 | mosaic 1.0, scale 0.5, 좌우 반전 확률 0.5, degrees 0 |

## 데이터 출처

### 사람: COCO 2017

FiftyOne Dataset Zoo의 coco-2017에서 person 클래스와 공식 detection 라벨을 수집했다. COCO train과 validation 분할을 사용하고 군중 라벨 및 유효하지 않은 좌표를 제외했다. v6에서는 v3의 사람 이미지와 정답 박스를 그대로 복사하고 해시로 보존 여부를 확인했다.

### 손동작: HaGRIDv2

이미지는 HaGRID 부분집합의 hagrid-export_100_images.zip 및 hagrid-export_1000_images.zip을 사용했다. 공식 주석을 이용해 three_gun은 finger_gun 양성, fist·peace·point는 음성으로 구성했다. 음성 이미지는 finger_gun 정답 박스가 없는 빈 라벨로 학습한다.

- 이미지 배포처: [GestureDetectionConnoisseurs/hagrid_subsets](https://huggingface.co/datasets/GestureDetectionConnoisseurs/hagrid_subsets)
- 공식 주석: [HaGRIDv2 annotations.zip](https://rndml-team-cv.obs.ru-moscow-1.hc.sbercloud.ru/datasets/hagrid_v2/annotations_with_landmarks/annotations.zip)

위 출처는 프로젝트의 데이터 생성 코드와 README_v6.md에 기록된 다운로드 출처다.

## 실제 데이터 구성

| 항목 | 수량 |
| --- | ---: |
| 학습 사람 이미지 | 1,099장 |
| 손동작 양성 학습 이미지 | 928장(기존 80장 + 신규 848장) |
| 일반 손동작 음성 학습 이미지 | 400장 |
| 학습 이미지 파일 합계 | 2,427장 |
| 학습 사람 정답 박스 | 3,539개 |
| 학습 finger_gun 정답 박스 | 928개 |
| 한 epoch 학습 목록 | 3,526개 |
| 기존 검증 이미지 | 244장(사람 이미지 224장 + 손동작 크롭 20장) |
| 기존 검증 사람 / finger_gun 박스 | 770개 / 20개 |
| 별도 손동작 평가 이미지 | 266장(양성 45장 + 음성 221장) |

사람 이미지 1,099장은 한 epoch에 2회 노출한다. 따라서 반복을 포함한 학습 목록 3,526개는 독립 이미지 파일 수 2,427장과 다르다. 학습 중 검증과 최고 체크포인트 선택에는 기존 244장 검증셋을 사용하며, 별도 266장 손동작 평가셋은 추가 비교와 임계값 분석에 사용했다.

## 전처리 및 분할

- HaGRID 공식 손 박스를 기준으로 손 주변을 크롭했다. 모델의 예측 박스를 정답 라벨로 사용하지 않았다.
- 신규 손 크롭은 640 기준 0.4·0.65·1.0 크기로 조정해 회색 배경에 배치했다. 이는 합성 크기 변화이며 실제 원거리 촬영 자료는 아니다.
- HaGRID는 완전한 사람 박스가 없으므로 손 크롭을 사람 전체 장면에 붙이지 않았다.
- 공식 user_id로 기존 검증 인물을 추가 학습에서 제외했다. 새 손동작 평가 인물은 v3·v5·v6 학습 인물과 겹치지 않게 구성했다.
- 기존 사람 이미지와 라벨의 보존, 사용자 분리, 반복 학습 목록, 평가셋 구성을 audit_v6.py로 검사했다.

## 저장된 평가 결과

comparison_v6.json의 v6 결과다. 서로 다른 평가셋의 수치를 하나의 전체 성능으로 합치지 않는다.

| 평가셋 / 클래스 | Precision | Recall | mAP50 | mAP50–95 |
| --- | ---: | ---: | ---: | ---: |
| 기존 검증셋 / person | 78.9% | 53.4% | 62.9% | 38.8% |
| 기존 검증셋 / finger_gun | 97.0% | 100.0% | 99.5% | 89.2% |
| 별도 손동작 평가셋 / finger_gun | 99.0% | 100.0% | 99.5% | 88.8% |

별도 일반 손동작 음성 221장 중 신뢰도 0.25에서 31장(14.0%)에 finger_gun 오탐이 있었다. 임계값 0.8에서는 양성 45/45장 탐지, 음성 오탐 0/221장이 기록됐다(rect=False, 위치 IoU 0.5 기준). 같은 평가셋을 보고 임계값을 선택했으므로 이 결과는 독립적인 최종 성능 검증이 아니다.

## ONNX 변환 및 산출물

finish_v6.py에서 best.pt를 ONNX로 변환했다. 설정은 입력 640 × 640, batch 1, dynamic=False, simplify=True, CPU export다. 기록상 ONNX 구조 검사와 사람/손동작 표본의 PT·ONNX 추론 비교를 통과했다. smoke_v6.json에는 두 표본의 클래스와 점수가 저장돼 있다.

| 산출물 | 로컬 경로(yolo_starter 기준) |
| --- | --- |
| PyTorch 가중치 | runs/person_finger_gun_v6/weights/best.pt |
| ONNX 가중치 | runs/person_finger_gun_v6/weights/best.onnx |
| 학습 설정 / 기록 | runs/person_finger_gun_v6/args.yaml / results.csv |
| 데이터 구성 기록 | dataset_v6/v6_manifest.json |
| 평가 / 임계값 / 변환 비교 | comparison_v6.json / threshold_v6.json / smoke_v6.json |

이 문서의 Git 업로드에는 대용량 데이터, 가상환경, 모델 가중치를 포함하지 않는다. 위 경로는 로컬 산출물 위치이며 저장소에 모두 포함돼 있다는 뜻은 아니다.

## 한계

사람 재현율은 53.4%로 누락이 남아 있다. 손 크롭은 실제 CCTV 장면과 다르고 일부 크롭에는 사람 라벨이 없는 몸통이 보일 수 있다. 별도 손동작 평가의 양성도 45장으로 적다. 실제 영상에서 작은 손·흐린 손·다양한 방향과 사람+손동작 동시 탐지를 추가 확인해야 한다. 높은 손동작 임계값을 사람 클래스에도 일괄 적용하면 사람 누락이 늘 수 있다.
