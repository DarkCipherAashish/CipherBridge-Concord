"""Shared visual styling for CipherBridge Concord."""
import streamlit as st

CSS = """
<style>
.stApp {background:linear-gradient(145deg,#08111f,#0b1424 55%,#101b30);color:#e6edf7}
[data-testid="stSidebar"]{background:#0b1220;border-right:1px solid #24344d}
[data-testid="stSidebar"] *{color:#dce7f7}
.hero{padding:25px;border:1px solid #263c5b;border-radius:18px;background:linear-gradient(120deg,#122541,#102b35);margin-bottom:20px}
.eyebrow{color:#53dfc1;font-weight:700;letter-spacing:2px;font-size:.8rem}
div[data-testid="stMetric"]{background:#111e31;border:1px solid #263b58;padding:12px;border-radius:12px}
.footer{color:#8095b2;text-align:center;padding:18px}
.section-card{padding:16px 18px;border:1px solid #263b58;border-radius:14px;background:rgba(17,30,49,.72);margin:8px 0 14px 0}
.step-label{font-size:.78rem;text-transform:uppercase;letter-spacing:1.4px;color:#53dfc1;font-weight:800}
.helper{color:#a8bad2;font-size:.92rem}

/* ---------- Chat bubbles ---------- */
div[data-testid="stChatMessage"]{background:rgba(17,30,49,.72);border:1px solid #263b58;border-radius:14px;padding:14px 16px;margin-bottom:10px}
div[data-testid="stChatMessage"]:has(.side-a){border-left:4px solid #53dfc1}
div[data-testid="stChatMessage"]:has(.side-b){border-left:4px solid #7aa7ff}
div[data-testid="stChatMessage"]:has(.notice-warn){border-left:4px solid #f5b94a}
div[data-testid="stChatMessage"]:has(.notice-info){border-left:4px solid #7aa7ff}
div[data-testid="stChatMessage"]:has(.notice-bad){border-left:4px solid #ff7a7a}
div[data-testid="stChatMessage"]:has(.concl-head){border:1px solid #2d8b7b;background:linear-gradient(120deg,rgba(16,73,73,.45),rgba(17,30,49,.92))}

/* ---------- Workspace header ---------- */
.ws-title{font-size:1.6rem;font-weight:800;margin:0}
.ws-sub{color:#a8bad2;margin:2px 0 10px 0}
.panel-strip{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:#a8bad2;font-size:.9rem;margin:2px 0 12px 0}
.panel-chip{padding:3px 11px;border:1px solid #263b58;border-radius:999px;background:#111e31;color:#dce7f7}

/* ---------- Turn headers & pills ---------- */
.turn-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:6px}
.speaker{font-weight:800;font-size:1.02rem}
.pill{font-size:.7rem;font-weight:800;letter-spacing:.8px;text-transform:uppercase;padding:2px 9px;border-radius:999px;border:1px solid transparent}
.pill-a{color:#53dfc1;border-color:#2d8b7b;background:rgba(83,223,193,.08)}
.pill-b{color:#7aa7ff;border-color:#3b5fa8;background:rgba(122,167,255,.08)}
.pill-phase{color:#c9d6ea;border-color:#34496a;background:rgba(255,255,255,.04)}
.turn-no{color:#8095b2;font-size:.8rem;margin-left:auto}

/* ---------- Notices ---------- */
.notice-title{font-weight:800;font-size:1.02rem;margin-bottom:2px}

/* ---------- Final conclusion ---------- */
.concl-head{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:6px}
.concl-head .eyebrow{font-size:.85rem}
.badge{font-size:.72rem;font-weight:800;letter-spacing:.6px;text-transform:uppercase;padding:3px 11px;border-radius:999px;border:1px solid transparent}
.badge-ok{color:#53dfc1;border-color:#2d8b7b;background:rgba(83,223,193,.12)}
.badge-warn{color:#f5b94a;border-color:#8a6a24;background:rgba(245,185,74,.12)}
.badge-bad{color:#ff7a7a;border-color:#8a3a3a;background:rgba(255,122,122,.12)}

/* ---------- Phase tracker ---------- */
.tracker{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:4px 0 10px 0}
.tracker .step{font-size:.76rem;font-weight:700;padding:3px 11px;border-radius:999px;border:1px solid #34496a;color:#8095b2}
.tracker .step-done{color:#53dfc1;border-color:#2d8b7b;background:rgba(83,223,193,.08)}
.tracker .step-active{color:#08111f;border-color:#53dfc1;background:#53dfc1}
.tracker .sep{color:#52698a}

/* ---------- How it works ---------- */
.how-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 14px 0}
.how-card{padding:12px 14px;border:1px solid #263b58;border-radius:12px;background:rgba(11,18,32,.7)}
.how-card b{display:block;color:#53dfc1;font-size:.78rem;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:3px}
.how-card span{color:#c9d6ea;font-size:.9rem}
@media (max-width:720px){.how-grid{grid-template-columns:1fr}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
