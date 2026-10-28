#!/usr/bin/env python3
"""Render explicitly authored hardware projections; never extracts C source."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(isa, name, initial, threads, condition):
    rows = []
    for i in range(max(map(len, threads))):
        rows.append(" | ".join(t[i] if i < len(t) else "" for t in threads) + " ;")
    return (f"{isa} {name}\n\n{{\n  " + ";\n  ".join(initial) + ";\n}\n\n"
            + " | ".join(f"P{i}" for i in range(len(threads))) + " ;\n"
            + "\n".join(rows) + f"\n\nexists ({condition})\n")


def models():
    for case, obligation in [("B01_spsc_ring", "publication"),
                             ("B01_spsc_ring", "recycling"),
                             ("B02_spinlock", "handoff")]:
        for variant in ("relaxed", "ordered"):
            ordered = variant == "ordered"
            name = f"{case}_{obligation}_{variant}"
            if obligation == "recycling":
                # Consumer must finish reading before returning a slot.
                xinit = ["data=1", "tail=0"]
                xt = [["MOV EAX,[data]", "MOV [tail],$1"],
                      ["MOV EAX,[tail]", "MOV [data],$2"]]
                rt = [["lw x10,0(x1)"] + (["fence rw,w"] if ordered else [])
                      + ["li x12,1", "sw x12,0(x2)"],
                      ["lw x10,0(x2)"] + (["fence r,rw"] if ordered else [])
                      + ["li x12,2", "sw x12,0(x1)"]]
                xc = "0:EAX=2 /\\ 1:EAX=1"
                rc = "0:x10=2 /\\ 1:x10=1"
            else:
                # Handoff starts with the writer already holding lock=1.
                flag_initial, published = (1, 0) if obligation == "handoff" else (0, 1)
                xinit = ["data=0", f"tail={flag_initial}"]
                xt = [["MOV [data],$1", f"MOV [tail],${published}"],
                      ["MOV EAX,[tail]", "MOV EBX,[data]"]]
                rt = [["li x12,1", "sw x12,0(x1)"]
                      + (["fence rw,w"] if ordered else [])
                      + [f"li x12,{published}", "sw x12,0(x2)"],
                      ["lw x10,0(x2)"] + (["fence r,rw"] if ordered else [])
                      + ["lw x11,0(x1)"]]
                xc = f"1:EAX={published} /\\ 1:EBX=0"
                rc = f"1:x10={published} /\\ 1:x11=0"
            rinit = xinit + [f"{i}:x1=data" for i in range(2)] + [f"{i}:x2=tail" for i in range(2)]
            yield f"{case}/model/{obligation}.{variant}.x86.litmus", render("X86", name+"_x86", xinit, xt, xc)
            yield f"{case}/model/{obligation}.{variant}.riscv.litmus", render("RISCV", name+"_riscv", rinit, rt, rc)


if __name__ == "__main__":
    for filename, content in models():
        (ROOT / filename).write_text(content)
