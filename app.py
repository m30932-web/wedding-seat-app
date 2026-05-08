import streamlit as st
import pandas as pd
import math
import re
import uuid
import copy
import json
import os

# =====================================================================
# 🛠️ 系統環境與權限設定區 (管理員專用)
# =====================================================================
SYSTEM_ENV = "Production"  # 已經為你預設為 Production 正式環境
ADMIN_PASSWORD = "666"  
BACKUP_FILE = f"wedding_seat_data_{SYSTEM_ENV}.json"
# =====================================================================

st.set_page_config(page_title=f"排座位系統", layout="wide")

st.markdown("""
    <style>
    .ballroom-floor { 
        background-color: #ffffff; border: 2px dashed #ccc; 
        position: relative; border-radius: 20px; margin-top: 20px; overflow: hidden;
        background-image: radial-gradient(#f0f0f0 1px, transparent 1px); background-size: 30px 30px;
        min-height: 600px;
    }
    .round-table-wrapper { position: absolute; width: 220px; height: 220px; transform: translate(-50%, -50%); z-index: 2; }
    .round-table-core {
        position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
        background: rgba(255, 255, 255, 0.95); border: 2px solid #ffb6c1; border-radius: 50%; 
        width: 130px; height: 130px; display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1); z-index: 2;
    }
    .seat-circle {
        position: absolute; width: 44px; height: 44px; border-radius: 50%; font-size: 13px; line-height: 42px; text-align: center; 
        transform: translate(-50%, -50%); overflow: hidden; white-space: nowrap; font-weight: bold;
        font-family: 'Microsoft JhengHei', sans-serif; color: #000000; box-shadow: 1px 1px 3px rgba(0,0,0,0.2);
        z-index: 3;
    }
    h4 { margin-bottom: 5px !important; font-family: 'Microsoft JhengHei', sans-serif; }
    div[data-testid="stButton"] button { padding: 0.25rem 0.5rem; }
    
    div[data-testid="element-container"]:has(+ div[data-testid="element-container"] #btn-wrapper) input { padding-right: 35px !important; }
    div[data-testid="element-container"]:has(#btn-wrapper) { display: none !important; }
    div[data-testid="element-container"]:has(#btn-wrapper) + div[data-testid="element-container"] {
        transform: translate(-8px, -55px); margin-bottom: -45px; display: flex; justify-content: flex-end; pointer-events: none; z-index: 10;
    }
    div[data-testid="element-container"]:has(#btn-wrapper) + div[data-testid="element-container"] button {
        pointer-events: auto; background-color: transparent !important; border: none !important;
        box-shadow: none !important; color: #b0b0b0 !important; font-size: 16px !important;
        padding: 0 !important; width: 30px !important; height: 38px !important; display: flex; align-items: center; justify-content: center; transition: color 0.2s ease;
    }
    div[data-testid="element-container"]:has(#btn-wrapper) + div[data-testid="element-container"] button:hover { color: #666666 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 核心邏輯函數 ---
def clean_name(name_str):
    s = re.sub(r'[👔👚👑💼🍵🎉👤❓✅]', '', str(name_str))
    s = re.sub(r'\(\d+\s*人\)', '', s)
    s = re.sub(r'\[.*?\]', '', s)
    return s.strip()

def create_table(header, row, col, capacity=10):
    return {"id": str(uuid.uuid4()), "header": header, "capacity": capacity, "row": float(row), "col": float(col)}

def get_icon_for_side(side_name):
    if "男" in side_name: return "👔"
    if "女" in side_name: return "👚"
    if "主" in side_name or "長官" in side_name or "貴賓" in side_name: return "👑"
    if "公" in side_name or "商" in side_name or "部" in side_name: return "💼"
    if "老" in side_name or "長" in side_name: return "🍵"
    if "朋" in side_name or "友" in side_name or "桌" in side_name: return "🎉"
    return "👤"

color_palette = ["#87CEEB", "#FFD700", "#FFB6C1", "#98FB98", "#DDA0DD", "#FFA07A", "#E6E6FA", "#F0E68C", "#AFEEEE", "#E0FFFF"]
def get_color_for_side(side_name):
    if side_name in st.session_state.guest_groups:
        idx = st.session_state.guest_groups.index(side_name)
        return color_palette[idx % len(color_palette)]
    return "#e0e0e0"

def is_duplicate_name(new_name, exclude_id=None):
    c_name = clean_name(new_name)
    for g in st.session_state.app_guests.values():
        if g['id'] != exclude_id and g['clean_name'] == c_name:
            return True
    return False

def get_next_table_name():
    existing_headers = [t['header'] for t in st.session_state.app_tables]
    base_num = len(st.session_state.app_tables) + 1
    candidate = f"第 {base_num} 桌"
    while candidate in existing_headers:
        base_num += 1
        candidate = f"第 {base_num} 桌"
    return candidate

# ================= 網頁列印導出 (支援手動調整比例) =================
def export_to_print_html(sys_title, tables, guests):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{sys_title} - 列印版</title>
        <style>
            body {{ font-family: 'Microsoft JhengHei', Arial, sans-serif; padding: 20px; color: #222; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            .title {{ text-align: center; font-size: 28px; color: #d63384; margin-bottom: 20px; font-weight: bold; border-bottom: 3px solid #d63384; padding-bottom: 10px; }}
            .table-container {{ display: flex; flex-wrap: wrap; justify-content: space-between; }}
            .table-box {{ width: 48%; border: 1px solid #333; border-radius: 8px; padding: 12px; margin-bottom: 15px; box-sizing: border-box; page-break-inside: avoid; }}
            .table-header {{ background-color: #f8f9fa; font-weight: bold; font-size: 18px; padding-bottom: 8px; border-bottom: 1px dashed #666; margin-bottom: 10px; }}
            .guest-list {{ display: flex; flex-wrap: wrap; gap: 5px; }}
            .guest-item {{ width: 45%; font-size: 14px; padding: 2px 0; }}
            
            .visual-map-section {{ page-break-before: always; text-align: center; width: 100%; }}
            .visual-map-title {{ font-size: 24px; margin: 30px 0 15px 0; font-weight: bold; }}
            
            .ballroom-floor-print-wrapper {{ width: 100%; display: flex; justify-content: center; margin-top: 20px; }}
            .ballroom-floor {{ background-color: #ffffff; border: 1px solid #ccc; position: relative; border-radius: 20px; overflow: hidden; background-image: radial-gradient(#f0f0f0 1px, transparent 1px); background-size: 30px 30px; transform-origin: top center; }}
            .round-table-wrapper {{ position: absolute; width: 220px; height: 220px; transform: translate(-50%, -50%); z-index: 2; }}
            .round-table-core {{ position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); background: rgba(255, 255, 255, 0.95); border: 2px solid #ffb6c1; border-radius: 50%; width: 130px; height: 130px; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); z-index: 2; }}
            .seat-circle {{ position: absolute; width: 44px; height: 44px; border-radius: 50%; font-size: 13px; line-height: 42px; text-align: center; transform: translate(-50%, -50%); overflow: hidden; white-space: nowrap; font-weight: bold; font-family: 'Microsoft JhengHei', sans-serif; color: #000000; box-shadow: 1px 1px 3px rgba(0,0,0,0.2); z-index: 3; }}
            
            .control-panel {{ background-color: #f1f3f5; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; border: 1px solid #dee2e6; }}
            @media print {{
                @page {{ size: A4 landscape; margin: 1cm; }}
                body {{ padding: 0; }}
                .control-panel {{ display: none !important; }}
                .table-box {{ border: 1px solid #000; }}
            }}
        </style>
    </head>
    <body>
        <div class="control-panel">
            <h3 style="margin-top:0; color:#333;">🖨️ 列印預覽與排版控制</h3>
            <label for="zoomSlider" style="font-weight:bold; font-size:16px;">桌位圖縮放比例：</label>
            <input type="range" id="zoomSlider" min="0.3" max="1.5" step="0.05" value="0.6" style="width: 300px; vertical-align: middle; margin: 0 15px;" 
                   oninput="document.getElementById('zoomValue').innerText = Math.round(this.value * 100) + '%'; document.getElementById('myBallroom').style.zoom = this.value;">
            <span id="zoomValue" style="font-weight:bold; display:inline-block; width:50px;">60%</span>
            <br><span style="font-size:13px; color:#666;">(若列印時圖形被切斷，請將比例調小，確認畫面完整後再點擊下方按鈕)</span><br><br>
            <button onclick="window.print()" style="background-color:#0d6efd; color:white; border:none; padding:10px 25px; font-size:18px; border-radius:5px; cursor:pointer; font-weight:bold;">馬上列印 (或另存PDF)</button>
        </div>

        <div class="title">{sys_title} - 桌位名單總表</div>
        <div class="table-container">
    """
    for t in tables:
        assigned = [g for g in guests.values() if g['table_id'] == t['id']]
        total_count = sum(g['count'] for g in assigned)
        html += f'<div class="table-box"><div class="table-header">{t["header"]} <span style="font-size:12px; font-weight:normal;">({total_count}/{t["capacity"]} 人)</span></div><div class="guest-list">'
        if not assigned: html += "<div class='guest-item' style='color:#999;'>(此桌尚無賓客)</div>"
        else:
            for g in assigned: html += f"<div class='guest-item'>● {g['raw_name']} ({g['count']}人)</div>"
        html += "</div></div>"
    html += "</div>"
    
    if tables:
        html += '<div class="visual-map-section"><div class="visual-map-title">廳房平面視覺圖</div>'
        max_r, max_c = max([t.get('row', 1) for t in tables]), max([t.get('col', 1) for t in tables])
        d_height, d_width = max(500, int(max_r * 280 + 100)), max(800, int(max_c * 280 + 100))
        html += f'<div class="ballroom-floor-print-wrapper"><div id="myBallroom" class="ballroom-floor" style="height: {d_height}px; width: {d_width}px; zoom: 0.6;">'
        for t in tables:
            cap, flat_seats = t['capacity'], []
            assigned_guests = [g for g in guests.values() if g['table_id'] == t['id']]
            for g in assigned_guests:
                for _ in range(g['count']): flat_seats.append((g['clean_name'], get_color_for_side(g['side'])))
            px_x, px_y = t['col'] * 280 - 140, t['row'] * 280 - 140
            html += f'<div class="round-table-wrapper" style="left:{px_x}px; top:{px_y}px;"><svg width="220" height="220" style="position:absolute; left:0; top:0; z-index:0; overflow:visible;">'
            current_s_idx = 0
            for g in assigned_guests:
                if current_s_idx >= cap: break
                count = min(g['count'], cap - current_s_idx)
                if count > 1:
                    color = get_color_for_side(g['side'])
                    a1, a2 = math.radians(current_s_idx * (360/cap) - 90), math.radians((current_s_idx + count - 1) * (360/cap) - 90)
                    if count >= cap: html += f'<circle cx="110" cy="110" r="95" stroke="{color}80" stroke-width="48" fill="none" />'
                    else:
                        x1, y1, x2, y2 = 110 + 95 * math.cos(a1), 110 + 95 * math.sin(a1), 110 + 95 * math.cos(a2), 110 + 95 * math.sin(a2)
                        html += f'<path d="M {x1} {y1} A 95 95 0 {1 if count > (cap/2.0) else 0} 1 {x2} {y2}" stroke="{color}80" stroke-width="48" fill="none" stroke-linecap="round" />'
                current_s_idx += count
            html += f'</svg><div class="round-table-core"><strong style="color: #d63384; font-size:14px; text-align:center;">{t["header"]}</strong><span style="font-size: 11px; color: {"#ff4b4b" if len(flat_seats) > cap else "#666"};">({len(flat_seats)}/{cap})</span></div>'
            for s_idx in range(cap):
                angle = math.radians(s_idx * (360/cap) - 90)
                cx, cy = 110 + 95 * math.cos(angle), 110 + 95 * math.sin(angle)
                if s_idx < len(flat_seats): html += f'<div class="seat-circle" style="left:{cx}px; top:{cy}px; background:{flat_seats[s_idx][1]}; border:1px solid #777;">{flat_seats[s_idx][0][:3]}</div>'
                else: html += f'<div class="seat-circle" style="left:{cx}px; top:{cy}px; background:#f3f3f3; border:1px solid #ddd;"></div>'
            html += '</div>'
        html += '</div></div></div>'
    html += "</body></html>"
    return html.encode('utf-8')

# ================= 2. 無損資料庫載入與平滑升級 =================
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.role = "Guest" 
    loaded = False
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state.guest_groups = data.get("guest_groups", ["男方", "主桌", "女方"])
                st.session_state.sys_categories = data.get("sys_categories", ["同事", "親戚", "大學同學", "高中同學"])
                st.session_state.app_tables = data.get("app_tables", [])
                st.session_state.app_guests = data.get("app_guests", {})
                st.session_state.sys_title = data.get("sys_title", "💖 通用排座位系統")
                st.session_state.app_versions = data.get("app_versions", {})
                loaded = True
        except: pass
    if not loaded:
        st.session_state.guest_groups = ["男方", "主桌", "女方"]
        st.session_state.sys_categories = ["同事", "親戚", "大學同學", "高中同學"]
        st.session_state.app_tables = [create_table("第 1 桌", 1.0, 1.0)]
        st.session_state.app_guests = {}
        st.session_state.app_versions = {}
        st.session_state.sys_title = "💖 通用排座位系統"

if 'edit_title_mode' not in st.session_state: st.session_state.edit_title_mode = False
if 'editing_guest' not in st.session_state: st.session_state.editing_guest = None
if 'search_t_kw' not in st.session_state: st.session_state.search_t_kw = ""
if 'grid_r' not in st.session_state: st.session_state.grid_r = 3
if 'grid_c' not in st.session_state: st.session_state.grid_c = 4

# --- 動態標題 UI 區塊 ---
col_t1, col_t2, col_print = st.columns([5, 1, 3])
if not st.session_state.edit_title_mode:
    with col_t1: st.markdown(f"<h1 style='margin-top:-15px; font-family: \"Microsoft JhengHei\", sans-serif;'>{st.session_state.sys_title}</h1>", unsafe_allow_html=True)
    with col_t2: 
        if st.button("✏️", help="點擊修改系統名稱"): st.session_state.edit_title_mode = True; st.rerun()
else:
    with col_t1: new_title = st.text_input("輸入新的系統名稱", value=st.session_state.sys_title, label_visibility="collapsed")
    with col_t2: 
        if st.button("💾 儲存"):
            if new_title.strip() != "": st.session_state.sys_title = new_title.strip()
            st.session_state.edit_title_mode = False; st.rerun()

# --- 匯出列印下載按鈕 ---
with col_print:
    st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
    html_data = export_to_print_html(st.session_state.sys_title, st.session_state.app_tables, st.session_state.app_guests)
    st.download_button(
        label="🖨️ 匯出列印版名單 (可自調比例)",
        data=html_data,
        file_name=f"{st.session_state.sys_title}_名單與圖面.html",
        mime="text/html",
        use_container_width=True
    )

st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)

# --- 指派與網格邏輯 ---
def handle_assignment_change(guest_id):
    new_t_id = st.session_state[f"sel_{guest_id}"]
    old_t_id = st.session_state.app_guests[guest_id]['table_id']
    if new_t_id == "未分配": st.session_state.app_guests[guest_id]['table_id'] = None; return
    if new_t_id != old_t_id:
        t = next((x for x in st.session_state.app_tables if x['id'] == new_t_id), None)
        if not t: st.session_state[f"sel_{guest_id}"] = "未分配"; st.session_state.app_guests[guest_id]['table_id'] = None; return
        g = st.session_state.app_guests[guest_id]
        current_occ = sum(x['count'] for x in st.session_state.app_guests.values() if x['table_id'] == new_t_id and x['id'] != guest_id)
        if current_occ + g['count'] > t['capacity']:
            st.toast(f"⚠️ 【{t['header']}】座位不足！", icon="⚠️")
            st.session_state[f"sel_{guest_id}"] = old_t_id if old_t_id else "未分配"
        else: st.session_state.app_guests[guest_id]['table_id'] = new_t_id

def update_tables_auto():
    target = st.session_state.target_tables_input
    current_len = len(st.session_state.app_tables)
    grid_cols = st.session_state.get('grid_c', 4)
    if target > current_len:
        for _ in range(current_len, target):
            curr = len(st.session_state.app_tables)
            st.session_state.app_tables.append(create_table(get_next_table_name(), 1.0 + (curr // grid_cols), 1.0 + (curr % grid_cols)))
    elif target < current_len:
        removed_ids = [t['id'] for t in st.session_state.app_tables[target:]]
        st.session_state.app_tables = st.session_state.app_tables[:target]
        for g in st.session_state.app_guests.values():
            if g['table_id'] in removed_ids: g['table_id'] = None

def add_one_table_cb():
    curr = len(st.session_state.app_tables)
    grid_cols = st.session_state.get('grid_c', 4)
    st.session_state.app_tables.append(create_table(get_next_table_name(), 1.0 + (curr // grid_cols), 1.0 + (curr % grid_cols)))
    st.session_state.target_tables_input = curr + 1

def delete_table_cb(t_id):
    t = next((x for x in st.session_state.app_tables if x['id'] == t_id), None)
    if t:
        for g in st.session_state.app_guests.values():
            if g['table_id'] == t_id: g['table_id'] = None
        st.session_state.app_tables.remove(t)
        st.session_state.target_tables_input = len(st.session_state.app_tables)

def load_version_cb():
    v_name = st.session_state.get("version_select")
    if v_name and v_name in st.session_state.app_versions:
        v_data = st.session_state.app_versions[v_name]
        st.session_state.app_tables = copy.deepcopy(v_data["tables"])
        st.session_state.app_guests = copy.deepcopy(v_data["guests"])
        st.session_state.guest_groups = copy.deepcopy(v_data.get("groups", st.session_state.guest_groups))
        st.session_state.target_tables_input = len(st.session_state.app_tables)
        st.toast(f"✅ 已載入版本：{v_name}")

def delete_version_cb():
    v_name = st.session_state.get("version_select")
    if v_name and v_name in st.session_state.app_versions:
        del st.session_state.app_versions[v_name]
        try:
            if os.path.exists(BACKUP_FILE):
                with open(BACKUP_FILE, "r", encoding="utf-8") as f: d = json.load(f)
                if "app_versions" in d and v_name in d["app_versions"]:
                    del d["app_versions"][v_name]
                    with open(BACKUP_FILE, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
        except: pass
        st.toast(f"🗑️ 已刪除版本：{v_name}")

def generate_grid_layout_cb():
    r, c = st.session_state.grid_r, st.session_state.grid_c
    total = r * c
    for i in range(total):
        row_val, col_val = 1.0 + (i // c), 1.0 + (i % c)
        if i < len(st.session_state.app_tables):
            st.session_state.app_tables[i]['row'], st.session_state.app_tables[i]['col'] = float(row_val), float(col_val)
            t_id = st.session_state.app_tables[i]['id']
            st.session_state[f"r_{t_id}"], st.session_state[f"l_{t_id}"] = float(row_val), float(col_val)
        else: st.session_state.app_tables.append(create_table(get_next_table_name(), row_val, col_val))
    if total < len(st.session_state.app_tables): st.session_state.app_tables = st.session_state.app_tables[:total]
    st.session_state.target_tables_input = total; st.rerun()

def sync_table(t_id):
    t = next((x for x in st.session_state.app_tables if x['id'] == t_id), None)
    if t:
        t['header'] = st.session_state.get(f"n_{t_id}", t['header'])
        t['capacity'] = st.session_state.get(f"c_{t_id}", t['capacity'])
        t['row'] = st.session_state.get(f"r_{t_id}", t['row'])
        t['col'] = st.session_state.get(f"l_{t_id}", t['col'])

# 3. 側邊欄控制中心
with st.sidebar:
    if st.session_state.role != "Admin":
        st.info("💡 **訪客模式**：您可以自由使用與儲存您的專屬方案，不影響系統預設主檔，資料僅會儲存在個人電腦中。")
        with st.expander("🔓 管理員解鎖", expanded=False):
            pwd = st.text_input("輸入管理密碼", type="password", key="login_pwd")
            if st.button("驗證身分", use_container_width=True):
                if pwd == ADMIN_PASSWORD: st.session_state.role = "Admin"; st.success("✅ 已取得最高權限！"); st.rerun()
                else: st.error("密碼錯誤！")
    else:
        st.success("👑 **管理員模式**：您的修改將成為官方主檔。")
        if st.button("🔒 返回訪客模式", use_container_width=True): st.session_state.role = "Guest"; st.rerun()
    st.divider()

    st.header("🗂️ 1. 系統分欄設定")
    with st.expander("⚙️ 調整分欄架構"):
        num_cols = st.number_input("分配區欄位數量", 1, 10, value=len(st.session_state.guest_groups))
        new_groups = []
        for i in range(num_cols):
            old_val = st.session_state.guest_groups[i] if i < len(st.session_state.guest_groups) else f"新分欄 {i+1}"
            new_groups.append(st.text_input(f"欄位 {i+1} 名稱", value=old_val, key=f"grp_input_{i}"))
        if st.button("🔄 套用設定", use_container_width=True):
            st.session_state.guest_groups = [ng.strip() for ng in new_groups if ng.strip()]
            st.rerun()

    st.header("👥 2. 賓客名單錄入")
    with st.expander("📂 批次匯入名單"):
        import_side = st.radio("歸屬分欄：", st.session_state.guest_groups, horizontal=True)
        uploaded_file = st.file_uploader("選擇 Excel/CSV", type=["xlsx", "csv"], label_visibility="collapsed")
        if uploaded_file and st.button("🚀 確認匯入"):
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                for _, row in df.iterrows():
                    n, c = str(row['姓名']), int(row.get('人數', 1))
                    cat = str(row.get('類別', '未分類'))
                    if is_duplicate_name(n): continue
                    g_id = str(uuid.uuid4())
                    st.session_state.app_guests[g_id] = {"id": g_id, "raw_name": n, "clean_name": clean_name(n), "count": c, "side": import_side, "icon": get_icon_for_side(import_side), "category": cat, "table_id": None, "source": "import"}
                st.success("匯入完成！")
            except Exception as e: st.error(f"錯誤：{e}")

        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️ 撤銷所有匯入名單", use_container_width=True):
            imported_ids = [k for k, v in st.session_state.app_guests.items() if v.get('source') == 'import']
            if imported_ids:
                for g_id in imported_ids: del st.session_state.app_guests[g_id]
                st.success("已撤銷所有匯入資料！")
                st.rerun()
            else:
                st.info("目前沒有匯入的名單可撤銷。")

    with st.expander("✍️ 手動新增單筆賓客", expanded=False):
        manual_side = st.radio("歸屬分欄：", st.session_state.guest_groups, horizontal=True, key="man_side")
        cat_options = st.session_state.sys_categories + ["(自訂新類別)"]
        manual_cat_sel = st.selectbox("類別：", cat_options)
        manual_cat = st.text_input("請輸入自訂類別名稱：") if manual_cat_sel == "(自訂新類別)" else manual_cat_sel

        col_n, col_c = st.columns([2, 1])
        m_name = col_n.text_input("姓名")
        m_count = col_c.number_input("人數", 1, 10, 1)
        
        if st.button("➕ 單筆加入", use_container_width=True):
            if m_name and manual_cat:
                if is_duplicate_name(m_name): st.error("❌ 賓客名稱已存在，請確認是否重複！")
                else:
                    if manual_cat not in st.session_state.sys_categories: st.session_state.sys_categories.append(manual_cat)
                    icon = get_icon_for_side(manual_side)
                    g_id = str(uuid.uuid4())
                    st.session_state.app_guests[g_id] = {
                        "id": g_id, "raw_name": m_name, "clean_name": clean_name(m_name), "count": m_count,
                        "side": manual_side, "icon": icon, "category": manual_cat, "table_id": None, "source": "manual"
                    }
                    st.rerun()
            elif not manual_cat: st.warning("⚠️ 請輸入自訂類別名稱！")

    st.header("📍 3. 廳房桌位管理")
    col_g1, col_g2 = st.columns(2)
    col_g1.number_input("總排數", 1, 30, key="grid_r")
    col_g2.number_input("每排桌數", 1, 20, key="grid_c")
    st.button("🔄 依網格重新排列", type="primary", use_container_width=True, on_click=generate_grid_layout_cb)
    st.divider()
    col_t1, col_t2 = st.columns(2)
    with col_t1: st.number_input("微調總桌數：", 1, 100, value=len(st.session_state.app_tables), key="target_tables_input", on_change=update_tables_auto)
    with col_t2: st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True); st.button("➕ 新增單桌", use_container_width=True, on_click=add_one_table_cb)
    st.text_input("🔍 搜尋桌次", key="search_t_kw", placeholder="輸入桌名...")
    for t in st.session_state.app_tables:
        if st.session_state.search_t_kw and st.session_state.search_t_kw.lower() not in t['header'].lower(): continue
        with st.expander(f"⚙️ {t['header']} 設定"):
            st.text_input("桌名", value=t['header'], key=f"n_{t['id']}", on_change=sync_table, args=(t['id'],))
            st.number_input("座位數", 1, 15, value=t['capacity'], key=f"c_{t['id']}", on_change=sync_table, args=(t['id'],))
            r_c1, r_c2 = st.columns(2)
            r_c1.number_input("排(Y)", -5.0, 30.0, float(t['row']), step=0.5, key=f"r_{t['id']}", on_change=sync_table, args=(t['id'],))
            r_c2.number_input("欄(X)", -5.0, 20.0, float(t['col']), step=0.5, key=f"l_{t['id']}", on_change=sync_table, args=(t['id'],))
            if st.button("🗑️ 刪除", key=f"del_{t['id']}", use_container_width=True): delete_table_cb(t['id']); st.rerun()

    st.header("💾 4. 佈局檔案與記憶庫")
    st.markdown("<span style='color:#d63384; font-weight:bold;'>👑 官方主檔管理 (雲端伺服器)</span>", unsafe_allow_html=True)
    if st.session_state.role == "Admin":
        v_name = st.text_input("版本名稱", placeholder="官方定稿版", label_visibility="collapsed")
        if st.button("📥 儲存為官方方案", use_container_width=True):
            if v_name: 
                st.session_state.app_versions[v_name] = {"tables": copy.deepcopy(st.session_state.app_tables), "guests": copy.deepcopy(st.session_state.app_guests), "groups": copy.deepcopy(st.session_state.guest_groups)}
                st.success(f"已儲存：{v_name}")
                
        if st.session_state.app_versions:
            st.write("📂 讀取 / 🗑️ 刪除 官方方案：")
            st.selectbox("選擇版本", list(st.session_state.app_versions.keys()), label_visibility="collapsed", key="version_select")
            c_v1, c_v2 = st.columns(2)
            with c_v1: st.button("📤 載入", use_container_width=True, on_click=load_version_cb)
            with c_v2: st.button("🗑️ 刪除", use_container_width=True, on_click=delete_version_cb)
    else:
        if st.session_state.app_versions:
            st.write("📂 讀取官方方案：")
            st.selectbox("選擇版本", list(st.session_state.app_versions.keys()), label_visibility="collapsed", key="version_select")
            st.button("📤 載入官方版本", use_container_width=True, on_click=load_version_cb)
        else:
            st.info("尚無官方方案。")

    st.divider()
    st.markdown("<span style='color:#0d6efd; font-weight:bold;'>💾 本機進度備份 (您的電腦)</span>", unsafe_allow_html=True)
    st.info("💡 所有身分皆可將當前排版下載為獨立檔案，或上傳先前的檔案接續編輯。")
    
    draft_json = json.dumps({
        "tables": st.session_state.app_tables, 
        "guests": st.session_state.app_guests, 
        "groups": st.session_state.guest_groups
    }, ensure_ascii=False, indent=2)
    
    st.download_button(
        label="📥 下載目前的排版進度檔 (.json)", 
        data=draft_json, 
        file_name="我的專屬座位草稿.json", 
        mime="application/json", 
        use_container_width=True
    )
    
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    uploaded_draft = st.file_uploader("📂 載入您之前的進度檔 (.json)", type="json", label_visibility="collapsed")
    if uploaded_draft and st.button("🚀 確認載入此進度", use_container_width=True):
        try:
            # 🔥 [核心修復] 改用 getvalue() 讀取位元組資料，徹底避開 Streamlit 檔案指標耗盡的 Bug！
            file_bytes = uploaded_draft.getvalue()
            data = json.loads(file_bytes.decode('utf-8'))
            
            st.session_state.app_tables = data.get("tables", [])
            st.session_state.app_guests = data.get("guests", {})
            st.session_state.guest_groups = data.get("groups", st.session_state.guest_groups)
            
            st.toast("✅ 進度載入成功！", icon="✅")
            st.rerun()
        except Exception as e:
            st.error(f"❌ 檔案讀取失敗，錯誤原因：{e}")

# 4. 主畫面佈局
st.subheader("1. 賓客座位分配區")
table_occupancy = {t['id']: 0 for t in st.session_state.app_tables}
for g in st.session_state.app_guests.values():
    if g['table_id'] in table_occupancy: table_occupancy[g['table_id']] += g['count']
status_texts = [f"<b>{t['header']}</b> (<span style='color:{'#e74c3c' if t['capacity']-table_occupancy[t['id']]<=0 else '#27ae60'};'>餘 {t['capacity']-table_occupancy[t['id']]}</span>)" for t in st.session_state.app_tables]
st.markdown(f"<div style='padding:12px; background-color:#f8f9fa; border-radius:8px; margin-bottom:20px; font-size:14px;'>📍 剩餘空位：{' ｜ '.join(status_texts)}</div>", unsafe_allow_html=True)

def display_guest_dropdowns(guests_list, column_obj, main_title, count, unassigned, search_key):
    with column_obj:
        html_title = f"""
        <div style="margin-bottom: 10px;">
            <h4 style="margin: 0; font-family: 'Microsoft JhengHei', sans-serif;">{main_title}</h4>
            <div style="font-size: 14px; color: #555; margin-top: 5px;">
                (共 {count} 人 / 未分配 <span style="color:#e74c3c; font-weight:bold;">{unassigned}</span> 人)
            </div>
        </div>
        """
        st.markdown(html_title, unsafe_allow_html=True)
        
        search_kw = st.text_input(f"搜尋 {main_title}", key=f"search_{search_key}", placeholder="🔍 輸入姓名或類別...", label_visibility="collapsed")
        if search_kw:
            guests_list = [g for g in guests_list if search_kw.lower() in g['raw_name'].lower() or search_kw.lower() in g['category'].lower()]
            
        with st.expander("🤖 依類別自動排座"):
            unassigned_guests = [g for g in guests_list if g['table_id'] is None]
            unassigned_cats = list(set([g['category'] for g in unassigned_guests]))
            if not unassigned_cats:
                st.info("目前無未分配的類別")
            else:
                sel_cat = st.selectbox("1. 選擇要群組的類別", unassigned_cats, key=f"auto_cat_{search_key}")
                cat_count = sum(g['count'] for g in unassigned_guests if g['category'] == sel_cat)
                avg_cap = sum(t['capacity'] for t in st.session_state.app_tables) / len(st.session_state.app_tables) if st.session_state.app_tables else 10
                rec_tables = max(1, math.ceil(cat_count / avg_cap))
                
                st.info(f"💡 此類別待排：**{cat_count}** 人 (建議選取 **{rec_tables}** 桌)")
                sel_tab_names = st.multiselect("2. 指定入座桌次 (可複選，依序填滿)", [t['header'] for t in st.session_state.app_tables], key=f"auto_tab_{search_key}")
                
                if st.button("🚀 一鍵排入", use_container_width=True, key=f"auto_btn_{search_key}"):
                    if not sel_tab_names: st.warning("請先選擇至少一個桌次！")
                    else:
                        target_tables = [next(t for t in st.session_state.app_tables if t['header'] == name) for name in sel_tab_names]
                        success_count, failed_count = 0, 0
                        for g in unassigned_guests:
                            if g['category'] == sel_cat:
                                assigned = False
                                for t_target in target_tables:
                                    t_id = t_target['id']
                                    if table_occupancy[t_id] + g['count'] <= t_target['capacity']:
                                        g['table_id'] = t_id
                                        st.session_state[f"sel_{g['id']}"] = t_id
                                        table_occupancy[t_id] += g['count']
                                        success_count += g['count']
                                        assigned = True
                                        break
                                if not assigned: failed_count += g['count']
                        
                        if success_count > 0: st.success(f"已成功將 {success_count} 人排入指定桌次！"); st.rerun()
                        if failed_count > 0: st.toast(f"⚠️ 空間不足：尚有 {failed_count} 人無法塞入所選桌次", icon="⚠️")

        with st.container(height=500):
            if not guests_list: st.caption("目前無名單")
            for g in guests_list:
                if st.session_state.editing_guest == g['id']:
                    st.markdown("<div style='padding:10px; background-color:#fff3cd; border-radius:8px; margin-bottom:10px;'>", unsafe_allow_html=True)
                    st.write("✏️ **修改賓客資料**")
                    edit_name = st.text_input("姓名", value=g['raw_name'], key=f"edit_n_{g['id']}", label_visibility="collapsed")
                    ec1, ec2 = st.columns(2)
                    edit_count = ec1.number_input("人數", min_value=1, value=g['count'], key=f"edit_c_{g['id']}", label_visibility="collapsed")
                    edit_cat = ec2.text_input("類別", value=g['category'], key=f"edit_cat_{g['id']}", label_visibility="collapsed")
                    
                    bc1, bc2 = st.columns(2)
                    if bc1.button("💾 儲存", key=f"save_{g['id']}", use_container_width=True):
                        if is_duplicate_name(edit_name, exclude_id=g['id']): st.error("名稱不可重複！")
                        else:
                            g['raw_name'], g['clean_name'], g['count'], g['category'] = edit_name, clean_name(edit_name), edit_count, edit_cat
                            if edit_cat not in st.session_state.sys_categories: st.session_state.sys_categories.append(edit_cat)
                            st.session_state.editing_guest = None
                            st.rerun()
                    if bc2.button("取消", key=f"cancel_{g['id']}", use_container_width=True):
                        st.session_state.editing_guest = None; st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    status_icon = "❓" if g['table_id'] is None else "✅"
                    if f"sel_{g['id']}" not in st.session_state or st.session_state[f"sel_{g['id']}"] != (g['table_id'] if g['table_id'] else "未分配"):
                        st.session_state[f"sel_{g['id']}"] = g['table_id'] if g['table_id'] else "未分配"
                    
                    def format_func(t_id):
                        if t_id == "未分配": return "--- 未分配 ---"
                        t = next((x for x in st.session_state.app_tables if x['id'] == t_id), None)
                        return t['header'] if t else "未知桌次"

                    gc1, gc2, gc3 = st.columns([6, 1, 1])
                    with gc1:
                        st.markdown(f"<div style='font-size:14px; margin-bottom: 2px; margin-top: 10px;'>{status_icon} {g['icon']} <b>{g['raw_name']}</b> ({g['count']}人) <span style='color:#666; font-size:12px;'>[{g['category']}]</span></div>", unsafe_allow_html=True)
                        st.selectbox(label=f"hl_{g['id']}", options=["未分配"] + [t['id'] for t in st.session_state.app_tables], format_func=format_func, key=f"sel_{g['id']}", label_visibility="collapsed", on_change=handle_assignment_change, args=(g['id'],))
                    with gc2:
                        st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
                        if st.button("✏️", key=f"edit_btn_{g['id']}", help="編輯"): st.session_state.editing_guest = g['id']; st.rerun()
                    with gc3:
                        st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_btn_{g['id']}", help="刪除"): del st.session_state.app_guests[g['id']]; st.rerun()

cols = st.columns(len(st.session_state.guest_groups))
for i, grp_name in enumerate(st.session_state.guest_groups):
    grp_guests = [g for g in st.session_state.app_guests.values() if g['side'] == grp_name]
    headcount = sum(g['count'] for g in grp_guests)
    unassigned = sum(g['count'] for g in grp_guests if g['table_id'] is None)
    display_guest_dropdowns(grp_guests, cols[i], f"{get_icon_for_side(grp_name)} {grp_name}", headcount, unassigned, f"grp_{i}")

st.divider(); st.subheader("2. 廳房圓桌視覺平面圖")
if st.session_state.app_tables:
    max_r, max_c = max([t.get('row', 1) for t in st.session_state.app_tables]), max([t.get('col', 1) for t in st.session_state.app_tables])
    d_height, d_width = max(500, int(max_r*280+100)), max(800, int(max_c*280+100))
    html_content = f'<div class="ballroom-floor" style="height:{d_height}px; width:{d_width}px; margin:0 auto;">'
    for t in st.session_state.app_tables:
        cap, flat_seats = t['capacity'], []
        assigned = [g for g in st.session_state.app_guests.values() if g['table_id'] == t['id']]
        for g in assigned:
            for _ in range(g['count']): flat_seats.append((g['clean_name'], get_color_for_side(g['side'])))
        px_x, px_y = t['col']*280-140, t['row']*280-140
        html_content += f'<div class="round-table-wrapper" style="left:{px_x}px; top:{px_y}px;"><svg width="220" height="220" style="position:absolute; left:0; top:0; z-index:0; overflow:visible;">'
        curr_idx = 0
        for g in assigned:
            count = min(g['count'], cap-curr_idx)
            if count > 1:
                color = get_color_for_side(g['side'])
                a1, a2 = math.radians(curr_idx*(360/cap)-90), math.radians((curr_idx+count-1)*(360/cap)-90)
                if count >= cap: html_content += f'<circle cx="110" cy="110" r="95" stroke="{color}80" stroke-width="48" fill="none" />'
                else: html_content += f'<path d="M {110+95*math.cos(a1)} {110+95*math.sin(a1)} A 95 95 0 {1 if count > cap/2 else 0} 1 {110+95*math.cos(a2)} {110+95*math.sin(a2)}" stroke="{color}80" stroke-width="48" fill="none" stroke-linecap="round" />'
            curr_idx += count
        html_content += f'</svg><div class="round-table-core"><strong style="color:#d63384; font-size:14px;">{t["header"]}</strong><span style="font-size:11px;">({len(flat_seats)}/{cap})</span></div>'
        for s_idx in range(cap):
            angle = math.radians(s_idx*(360/cap)-90)
            cx, cy = 110+95*math.cos(angle), 110+95*math.sin(angle)
            if s_idx < len(flat_seats): html_content += f'<div class="seat-circle" style="left:{cx}px; top:{cy}px; background:{flat_seats[s_idx][1]}; border:1px solid #777;">{flat_seats[s_idx][0][:3]}</div>'
            else: html_content += f'<div class="seat-circle" style="left:{cx}px; top:{cy}px; background:#f3f3f3; border:1px solid #ddd;"></div>'
        html_content += '</div>'
    html_content += '</div>'
    st.markdown(html_content, unsafe_allow_html=True)

# 終極防護：管理員動作寫入
if st.session_state.role == "Admin":
    try:
        d = {}
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE, "r", encoding="utf-8") as f: d = json.load(f)
        d.update({"guest_groups": st.session_state.guest_groups, "sys_categories": st.session_state.sys_categories, "app_tables": st.session_state.app_tables, "app_guests": st.session_state.app_guests, "sys_title": st.session_state.sys_title})
        with open(BACKUP_FILE, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
    except: pass