#!/usr/bin/env sh
# PR이 spec 서브모듈 포인터를 잘못 옮기지 않았는지 검사한다 (finance-simulater/backend#41).
#
# 사용법: check_spec_pointer.sh <base_pointer> <head_pointer> <spec_dir>
#   base_pointer: PR base 브랜치의 spec 포인터 (git rev-parse <base_sha>:spec)
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

BASE="$1"
HEAD="$2"
SPEC_DIR="$3"

fail() {
    echo "::error::spec 서브모듈 포인터 검사 실패: $1" >&2
    echo "  base 포인터: $BASE" >&2
    echo "  head 포인터: $HEAD" >&2
    echo "  기능 브랜치에서 spec 포인터를 바꾸지 않았다면 main 기준으로 되돌리세요:" >&2
    echo "    git fetch origin && git checkout origin/main -- spec && git commit -m \"chore: spec 포인터 원복\"" >&2
    exit 1
}

has_commit() {
    git -C "$SPEC_DIR" cat-file -e "$1^{commit}" 2>/dev/null
}

if [ "$BASE" = "$HEAD" ]; then
    echo "spec 포인터 변경 없음 ($HEAD)"
    exit 0
fi

if ! has_commit "$HEAD" || ! git -C "$SPEC_DIR" merge-base --is-ancestor "$HEAD" origin/main; then
    fail "head 포인터가 spec main 히스토리에 없는 커밋 (push되지 않은 로컬 커밋이거나 spec 기능 브랜치 커밋)"
fi

# base 포인터가 spec에 없는 커밋이면(main이 이미 깨진 상태) 비교 기준이 없으므로 되돌림 검사를 건너뛴다.
# 이 경우 head가 spec main 커밋이기만 하면 복구 PR로 보고 통과시킨다.
if ! has_commit "$BASE"; then
    echo "base 포인터($BASE)가 spec에 없는 커밋 — 복구 PR로 보고 되돌림 검사 생략"
    exit 0
fi

if ! git -C "$SPEC_DIR" merge-base --is-ancestor "$BASE" "$HEAD"; then
    fail "head 포인터가 base 포인터보다 앞선 커밋이 아님 (예전 커밋으로 되돌림 또는 갈라진 히스토리)"
fi

echo "spec 포인터 정상 이동: $BASE → $HEAD"
