#!/usr/bin/env sh
# check_spec_pointer.sh 회귀 테스트 (finance-simulater/backend#41).
# 임시 git 레포에 spec main·기능 브랜치 히스토리를 만들고 포인터 조합별 통과/실패를 확인한다.
#
#   m1 ── m2 ── m3   (main)
#    └── f1           (feature — main에 merge되지 않음)
#   MISSING           (어디에도 없는 커밋 — push되지 않은 로컬 커밋 역할)
set -eu

CHECK="$(cd "$(dirname "$0")" && pwd)/check_spec_pointer.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git_q() { git -c user.name=test -c user.email=test@example.com -c init.defaultBranch=main "$@" >/dev/null 2>&1; }

git_q init "$WORK/origin"
commit() { git_q -C "$WORK/origin" commit --allow-empty -m "$1"; git -C "$WORK/origin" rev-parse HEAD; }
M1=$(commit m1)
M2=$(commit m2)
M3=$(commit m3)
git_q -C "$WORK/origin" checkout -b feature "$M1"
F1=$(commit f1)
git_q -C "$WORK/origin" checkout main
MISSING=0123456789abcdef0123456789abcdef01234567

# CI처럼 origin/main이 있는 clone에서 검사한다
git_q clone "$WORK/origin" "$WORK/spec"

failures=0
expect() { # expect <pass|fail> <설명> <base> <head>
    if sh "$CHECK" "$3" "$4" "$WORK/spec" >/dev/null 2>&1; then actual=pass; else actual=fail; fi
    if [ "$actual" = "$1" ]; then
        echo "ok   - $2"
    else
        echo "FAIL - $2 (기대 $1, 실제 $actual)"
        failures=$((failures + 1))
    fi
}

expect pass "포인터 동일" "$M3" "$M3"
expect pass "main에서 앞으로 이동" "$M1" "$M3"
expect fail "main에서 예전 커밋으로 되돌림" "$M3" "$M1"
expect fail "head가 spec 기능 브랜치 커밋" "$M3" "$F1"
expect fail "head가 어디에도 없는 커밋" "$M3" "$MISSING"
expect pass "깨진 base(없는 커밋) → main 커밋으로 복구" "$MISSING" "$M2"
expect pass "깨진 base(기능 브랜치 커밋) → main 커밋으로 복구" "$F1" "$M3"
expect fail "깨진 base → 기능 브랜치 커밋 (복구라도 main 커밋이어야 함)" "$MISSING" "$F1"

if [ "$failures" -ne 0 ]; then
    echo "${failures}개 케이스 실패" >&2
    exit 1
fi
echo "모든 케이스 통과"
