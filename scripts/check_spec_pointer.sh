#!/usr/bin/env sh
# PR이 spec 서브모듈 포인터를 잘못 옮기지 않았는지 검사한다 (finance-simulater/backend#41).
#
# 사용법: check_spec_pointer.sh <base_pointer> <head_pointer> <spec_dir>
#   base_pointer: PR base의 spec 포인터 (merge 커밋의 첫 번째 부모: git rev-parse HEAD^1:spec)
#   head_pointer: PR merge 결과의 spec 포인터 (git rev-parse HEAD:spec)
#   spec_dir:     origin/main을 포함한 히스토리 전체가 있는 spec 레포 clone
#
# 통과 조건 (포인터가 바뀐 경우):
#   1. head 포인터가 spec main 히스토리에 있다 — 로컬 커밋·spec 기능 브랜치 커밋 차단
#   2. head 포인터가 base 포인터의 후손이다 — 예전 커밋으로 되돌림 차단
set -eu

if [ "$#" -ne 3 ]; then
    echo "사용법: $0 <base_pointer> <head_pointer> <spec_dir>" >&2
    exit 2
fi

BASE_PTR="$1"
HEAD_PTR="$2"
SPEC_DIR="$3"

fail() {
    echo "::error::spec 서브모듈 포인터 검사 실패: $1" >&2
    echo "  base 포인터: $BASE_PTR" >&2
    echo "  head 포인터: $HEAD_PTR" >&2
    echo "  - 포인터를 바꿀 의도가 없었다면 main 기준으로 되돌리세요:" >&2
    echo "      git fetch origin && git checkout origin/main -- spec && git commit -m \"chore: spec 포인터 원복\"" >&2
    echo "  - 스펙 변경을 반영하려던 거라면 spec PR을 먼저 spec main에 merge한 뒤, 그 merge 커밋으로 포인터를 옮기세요." >&2
    exit 1
}

# 커밋이 spec main 히스토리에 있는지. spec_dir에 아예 없는 커밋(push 안 된 로컬 커밋)도 false.
in_spec_main() {
    git -C "$SPEC_DIR" cat-file -e "$1^{commit}" 2>/dev/null &&
        git -C "$SPEC_DIR" merge-base --is-ancestor "$1" origin/main
}

if [ "$BASE_PTR" = "$HEAD_PTR" ]; then
    echo "spec 포인터 변경 없음 ($HEAD_PTR)"
    exit 0
fi

if ! in_spec_main "$HEAD_PTR"; then
    fail "head 포인터가 spec main 히스토리에 없는 커밋 (push되지 않은 로컬 커밋이거나 spec 기능 브랜치 커밋)"
fi

# base 포인터가 spec main에 없는 커밋이면(main이 이미 깨진 상태 — 원격에 없는 커밋이든 spec 기능 브랜치
# 커밋이든) 비교 기준으로 쓸 수 없으므로 되돌림 검사를 건너뛴다. head가 spec main 커밋이면 복구 PR로 보고 통과.
if ! in_spec_main "$BASE_PTR"; then
    echo "base 포인터($BASE_PTR)가 spec main에 없는 커밋 — 복구 PR로 보고 되돌림 검사 생략"
    exit 0
fi

if ! git -C "$SPEC_DIR" merge-base --is-ancestor "$BASE_PTR" "$HEAD_PTR"; then
    fail "head 포인터가 base 포인터보다 앞선 커밋이 아님 (예전 커밋으로 되돌림 또는 갈라진 히스토리)"
fi

echo "spec 포인터 정상 이동: $BASE_PTR → $HEAD_PTR"
