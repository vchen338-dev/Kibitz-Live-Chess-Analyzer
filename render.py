import chess
import chess.svg

from theme import ARROW_COLORS, BOARD_COLORS, MONO, MUTED, RANK_COLORS, TEXT

ARROW_STYLE = """
    .arrow {
        stroke-width: 4px;
        stroke-linecap: round;
        stroke-linejoin: round;
        fill-opacity: 0.9;
        stroke-opacity: 0.9;
    }
"""


def _square_labels(flipped):
    """Coordinate labels inside the squares (viewBox is 360 = 8 x 45)."""
    files = "hgfedcba" if flipped else "abcdefgh"
    ranks = "12345678" if flipped else "87654321"
    out = []
    for i in range(8):
        tone = "#6d7a6b" if (i + 7) % 2 == 0 else "#e3dfd2"     # file letter, bottom row
        out.append(
            f'<text x="{i * 45 + 41}" y="{7 * 45 + 42}" font-family="Segoe UI, sans-serif" '
            f'font-size="8.5" font-weight="600" fill="{tone}" text-anchor="end">{files[i]}</text>'
        )
        tone = "#6d7a6b" if i % 2 == 0 else "#e3dfd2"           # rank number, left column
        out.append(
            f'<text x="3" y="{i * 45 + 11}" font-family="Segoe UI, sans-serif" '
            f'font-size="8.5" font-weight="600" fill="{tone}">{ranks[i]}</text>'
        )
    return "".join(out)


def build_board_svg(board, flipped, results):
    """Board SVG with last move, coordinates, and arrows + number tags for `results`."""
    arrows, badges = [], ""
    for i, result in enumerate(results[:3]):
        uci = result.get("move_uci")
        if not uci:
            continue
        move = chess.Move.from_uci(uci)
        arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color=ARROW_COLORS[i]))

        file_idx = chess.square_file(move.from_square)
        rank_idx = chess.square_rank(move.from_square)
        col = 7 - file_idx if flipped else file_idx
        row = rank_idx if flipped else 7 - rank_idx

        bx, by = col * 45 + 27, row * 45 + 2
        badges += (
            f'<g><rect x="{bx}" y="{by}" width="16" height="16" rx="3" '
            f'fill="{ARROW_COLORS[i]}" stroke="#101113" stroke-width="1"/>'
            f'<text x="{bx + 8}" y="{by + 12}" font-family="Consolas, monospace" '
            f'font-size="11" font-weight="700" fill="#101113" text-anchor="middle">{i + 1}</text></g>'
        )

    svg = chess.svg.board(
        board,
        flipped=flipped,
        arrows=arrows,
        lastmove=board.peek() if board.move_stack else None,
        colors=BOARD_COLORS,
        coordinates=False,
        size=640,
        style=ARROW_STYLE,
    )
    return svg.replace("</svg>", f"{_square_labels(flipped)}{badges}</svg>")


def lines_html(results):
    """Rich-text table of the top engine lines."""
    rows = []
    for i, r in enumerate(results[:3]):
        weight = 700 if i == 0 else 500
        pv = r["principal_variation"]
        pv = pv if len(pv) <= 56 else pv[:55].rstrip() + "…"
        rows.append(
            f'<tr>'
            f'<td style="color:{RANK_COLORS[i]}; font-family:{MONO}; padding:3px 14px 3px 0;">{i + 1}</td>'
            f'<td style="color:{TEXT}; font-family:{MONO}; font-weight:{weight}; padding:3px 18px 3px 0;">{r["best_move"]}</td>'
            f'<td style="color:{RANK_COLORS[i]}; font-family:{MONO}; padding:3px 18px 3px 0;">{r["eval_text"]}</td>'
            f'<td style="color:{MUTED}; font-family:{MONO}; font-size:9pt; padding:3px 0;">{pv}</td>'
            f'</tr>'
        )
    return f'<table cellspacing="0">{"".join(rows)}</table>'