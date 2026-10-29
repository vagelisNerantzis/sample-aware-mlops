"""Render the architecture as deterministic SVG using the standard library."""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape


def _text(x: int, y: int, value: str, css_class: str = "label") -> str:
    """Create a text element without allowing markup in its content."""
    return f'<text x="{x}" y="{y}" class="{css_class}">{escape(value)}</text>'


def _node(
    y: int,
    title: str,
    subtitle: str = "",
    *,
    height: int = 54,
    css_class: str = "node",
) -> list[str]:
    """Create a central workflow node with an optional explanatory line."""
    top = y + (28 if subtitle else 33)
    elements = [
        f'<rect x="310" y="{y}" width="570" height="{height}" rx="10" class="{css_class}"/>',
        _text(595, top, title, "node-label"),
    ]
    if subtitle:
        elements.append(_text(595, y + 51, subtitle, "node-detail"))
    return elements


def render_svg() -> str:
    """Return byte-stable architecture markup without environment inputs."""
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="1340" viewBox="0 0 1280 1340" role="img" aria-labelledby="title description">',
        '<title id="title">Sample-Centric ML: sample identity across the ML lifecycle</title>',
        '<desc id="description">Physical samples flow through a sample registry, dataset manifest, experiment specification, validation gates, representation, acquisition, inference, evaluation, run registry, promotion, simulation deployment, and monitoring. Monitoring motivates re-evaluation. Four companion repositories are associated with their conceptual execution stages.</desc>',
        '<defs>',
        '<marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L9 4.5 L0 9 Z" fill="#42546a"/></marker>',
        '<style>',
        'text{font-family:Arial,Helvetica,sans-serif;fill:#182b43}',
        '.title{font-size:29px;font-weight:700}.subtitle{font-size:16px;fill:#50647c}',
        '.node{fill:#f3f7fb;stroke:#9eafc2;stroke-width:1.5}',
        '.governance{fill:#e9f1ff;stroke:#6b91c8;stroke-width:1.5}',
        '.monitor{fill:#eaf6ef;stroke:#7da88b;stroke-width:1.5}',
        '.node-label{font-size:18px;font-weight:700;text-anchor:middle}',
        '.node-detail{font-size:13px;text-anchor:middle;fill:#50647c}',
        '.group{fill:#fbfcfe;stroke:#6b91c8;stroke-width:2}',
        '.group-label{font-size:15px;font-weight:700;letter-spacing:1px}',
        '.stage{fill:white;stroke:#aab7c7;stroke-width:1.2}',
        '.stage-label{font-size:16px;text-anchor:middle}',
        '.repo{font-size:13px;fill:#425b7a}.repo-caption{font-size:12px;fill:#687b91}',
        '.flow{fill:none;stroke:#42546a;stroke-width:2;marker-end:url(#arrow)}',
        '.association{stroke:#9baabe;stroke-width:1.4;stroke-dasharray:4 4}',
        '.loop{fill:none;stroke:#7b9385;stroke-width:2;marker-end:url(#arrow)}',
        '.loop-label{font-size:15px;font-weight:700;text-anchor:middle;fill:#456851}',
        '.footnote{font-size:13px;fill:#50647c}',
        '</style>',
        '</defs>',
        '<rect width="1280" height="1340" fill="#ffffff"/>',
        _text(55, 49, "Sample-Centric ML", "title"),
        _text(55, 80, "Physical sample identity survives every stage of the lifecycle.", "subtitle"),
        '<path d="M310 1217 H125 V504 H310" class="loop"/>',
    ]
    lines.extend(_node(125, "PHYSICAL SAMPLES"))
    lines.extend(_node(210, "SAMPLE REGISTRY"))
    lines.extend(_node(295, "DATASET / MODALITY MANIFEST"))
    lines.extend(_node(380, "EXPERIMENT SPECIFICATION"))
    lines.extend(_node(465, "VALIDATION GATES", "Leakage / provenance / reproducibility / quality", height=78, css_class="governance"))
    for start, end in [(179, 210), (264, 295), (349, 380), (434, 465), (543, 590)]:
        lines.append(f'<path d="M595 {start} V{end}" class="flow"/>')
    lines.extend([
        '<rect x="260" y="590" width="670" height="265" rx="12" class="group"/>',
        _text(285, 618, "ML EXECUTION / SAMPLE-LINKED ADAPTER OUTPUTS", "group-label"),
    ])
    stages = (
        (635, "Representation", ("multimodal-representation-", "learning")),
        (685, "Optional acquisition", ("adaptive-modality-", "acquisition")),
        (735, "Sample-level inference", ("multimodal-inference-demo",)),
        (785, "Evaluation / calibration", ("scientific-ml-benchmarking",)),
    )
    for y, title, repository in stages:
        lines.append(f'<rect x="310" y="{y}" width="570" height="35" rx="6" class="stage"/>')
        lines.append(_text(595, y + 24, title, "stage-label"))
        lines.append(f'<line x1="880" y1="{y + 17}" x2="955" y2="{y + 17}" class="association"/>')
        for index, label in enumerate(repository):
            lines.append(_text(968, y + 17 + index * 16, label, "repo"))
    for y in (670, 720, 770):
        lines.append(f'<path d="M595 {y} V{y + 15}" class="flow"/>')
    lines.append(_text(968, 850, "Conceptual companion roles", "repo-caption"))
    lines.extend(_node(900, "RUN REGISTRY"))
    lines.extend(_node(985, "PROMOTION LIFECYCLE", "Validated -> candidate -> explicit approval", height=80, css_class="governance"))
    lines.extend(_node(1100, "DEPLOYMENT / SIMULATION"))
    lines.extend(_node(1185, "MONITORING", "Modality availability / confidence / acquisition cost", height=65, css_class="monitor"))
    for start, end in [(855, 900), (954, 985), (1065, 1100), (1154, 1185)]:
        lines.append(f'<path d="M595 {start} V{end}" class="flow"/>')
    lines.extend([
        '<rect x="24" y="912" width="202" height="90" rx="8" fill="#ffffff"/>',
        _text(125, 938, "RE-EVALUATION", "loop-label"),
        _text(125, 963, "Review new evidence;", "node-detail"),
        _text(125, 984, "repeat the gates", "node-detail"),
        _text(55, 1300, "Control plane: lineage, deterministic identity, gates, provenance, registry, promotion, monitoring.", "footnote"),
        _text(55, 1322, "Synthetic adapters are standalone demonstrations; companion repositories are not runtime dependencies.", "footnote"),
        '</svg>',
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    """Write the diagram, or validate its bytes with ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed SVG differs")
    args = parser.parse_args()
    destination = Path(__file__).with_name("architecture.svg")
    expected = render_svg().encode("utf-8")
    if args.check:
        if not destination.exists() or destination.read_bytes() != expected:
            parser.exit(1, "Architecture SVG differs; regenerate it.\n")
        print("Architecture SVG matches the deterministic generator.")
        return 0
    destination.write_bytes(expected)
    print("Generated assets/architecture.svg.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
