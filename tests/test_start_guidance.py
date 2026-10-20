from pathlib import Path
import pytest

@pytest.mark.parametrize('name',['index.html','onboarding.js'])
def test_start_guidance_matches_entry_and_standard_paths(name):
    source=(Path(__file__).resolve().parents[1]/'public'/name).read_text()
    for phrase in ['시작 수준','4단계 첫 안내','모든 체스 규칙을 다루지는 않습니다','최대 6문항 입문 관찰','24문항 균형 진단','12문항 간이 진단','표준 재진단','진행 중인 진단은 먼저 이어서 완료']:
        assert phrase in source
