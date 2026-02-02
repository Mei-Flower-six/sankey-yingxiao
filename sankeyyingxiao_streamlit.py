# sankeyyingxiao_streamlit.py
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
import logging
import streamlit as st
from datetime import datetime
import json

# ===================== 1. 页面配置和基础配置 =====================
st.set_page_config(
    page_title="联盟营销平台转化链路分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 颜色配置（每个平台对应专属颜色）
GROUP_COLORS = {
    "红人": "#9290E6",
    "红人合作数量": "#9290E6",
    "测评类网站": "#4ECDC4",
    "测评类网站合作数量": "#4ECDC4",
    "联盟客": "#45B7D1",
    "联盟客合作数量": "#45B7D1",
    "折扣网站": "#96CEB4",
    "折扣网站合作数量": "#96CEB4",
    "Deals 网站": "#FFA726",
    "Deals 网站合作数量": "#FFA726",
    "Deals网站": "#FFA726",
    "Deals网站合作数量": "#FFA726",
    "总数量": "#1C363F",
    "总clicks": "#87CEEB",
    "总orders": "#FF6B6B",
    "总sales": "#DDA0DD",
    "默认": "rgba(200, 200, 200, 0.2)"
}

# ===================== 2. 读取Excel+生成专属合作数量链路 =====================
@st.cache_data
def read_excel_and_generate_sankey_data(file_path):
    try:
        df = pd.read_excel(file_path)
        logger.info(f"✅ 成功读取Excel文件，共{len(df)}行数据")
    except Exception as e:
        logger.error(f"❌ 读取Excel失败：{str(e)}")
        st.error(f"❌ 读取Excel失败：{str(e)}")
        return [], [], {}

    data_raw = []
    all_nodes = []

    for _, row in df.iterrows():
        platform_type = str(row.get("联盟营销平台类型", "")).strip()
        coop_count = float(row.get("合作数量", 0)) if pd.notna(row.get("合作数量")) else 0.0
        click_count = float(row.get("求和项:Clicks", 0)) if pd.notna(row.get("求和项:Clicks")) else 0.0
        order_count = float(row.get("求和项:Orders", 0)) if pd.notna(row.get("求和项:Orders")) else 0.0
        sales = float(row.get("求和项:Sales", 0)) if pd.notna(row.get("求和项:Sales")) else 0.0

        if not platform_type or platform_type == "nan":
            continue

        platform_coop_node = f"{platform_type}合作数量"

        # 收集所有节点
        current_nodes = [
            platform_type,
            platform_coop_node,
            "总数量",
            f"{platform_type}clicks",
            "总clicks",
            f"{platform_type}orders",
            "总orders",
            f"{platform_type}sales",
            "总sales"
        ]
        all_nodes.extend(current_nodes)

        # 生成8条链路
        data_raw.append([platform_type, platform_coop_node, coop_count, platform_type])
        data_raw.append([platform_coop_node, "总数量", coop_count, platform_type])
        data_raw.append(["总数量", f"{platform_type}clicks", click_count, platform_type])
        data_raw.append([f"{platform_type}clicks", "总clicks", click_count, platform_type])
        data_raw.append(["总clicks", f"{platform_type}orders", order_count, platform_type])
        data_raw.append([f"{platform_type}orders", "总orders", order_count, platform_type])
        data_raw.append(["总orders", f"{platform_type}sales", sales, platform_type])
        data_raw.append([f"{platform_type}sales", "总sales", sales, platform_type])

    all_nodes = list(set([node for node in all_nodes if node and str(node) != "nan"]))
    logger.info(f"✅ 生成桑基图数据完成，共{len(data_raw)}条链路，{len(all_nodes)}个节点")
    
    # 计算原始的总节点流入量（用于百分比计算）
    df_temp = pd.DataFrame(data_raw, columns=["source", "target", "value", "group"])
    df_temp["value"] = pd.to_numeric(df_temp["value"], errors="coerce").fillna(0.0)

    # 计算原始总流入
    original_total_incoming = df_temp.groupby("target")["value"].sum().to_dict()

    return data_raw, all_nodes, original_total_incoming

# ===================== 3. 应用标题 =====================
st.title("🤝 联盟营销平台转化链路分析")
st.markdown("---")

# 初始化session state
if 'search_keyword' not in st.session_state:
    st.session_state.search_keyword = ""

# ===================== 4. 侧边栏控制面板 =====================
with st.sidebar:
    st.header("⚙️ 控制面板")
    
    # 文件上传
    uploaded_file = st.file_uploader("上传Excel文件", type=["xlsx", "xls"])
    
    # 搜索区域
    search_keyword = st.text_input(
        "🔍 链路搜索（支持平台类型/节点关键词）",
        value=st.session_state.search_keyword,
        placeholder="输入关键词（如：红人、联盟客、总clicks...）",
        help="支持平台类型或节点关键词搜索"
    )
    
    # 更新session state
    st.session_state.search_keyword = search_keyword
    
    # 清空搜索按钮 - 修复API弃用警告
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 清空搜索", type="secondary", use_container_width=True):
            st.session_state.search_keyword = ""
            st.rerun()
    
    with col2:
        if st.button("🔄 刷新数据", type="primary", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    st.subheader("📏 缩放控制")
    
    # 初始化缩放系数
    if 'coop_scale' not in st.session_state:
        st.session_state.coop_scale = 1.0
    if 'clicks_scale' not in st.session_state:
        st.session_state.clicks_scale = 1.0
    if 'orders_scale' not in st.session_state:
        st.session_state.orders_scale = 1.0
    if 'sales_scale' not in st.session_state:
        st.session_state.sales_scale = 1.0
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.coop_scale = st.number_input(
            "合作数量链路缩放",
            min_value=0.01,
            max_value=10.0,
            value=st.session_state.coop_scale,
            step=0.1,
            help="调整合作数量链路的宽度"
        )
    
    with col2:
        st.session_state.clicks_scale = st.number_input(
            "Clicks链路缩放",
            min_value=0.01,
            max_value=10.0,
            value=st.session_state.clicks_scale,
            step=0.1,
            help="调整Clicks链路的宽度"
        )
    
    col3, col4 = st.columns(2)
    with col3:
        st.session_state.orders_scale = st.number_input(
            "Orders链路缩放",
            min_value=0.01,
            max_value=10.0,
            value=st.session_state.orders_scale,
            step=0.1,
            help="调整Orders链路的宽度"
        )
    
    with col4:
        st.session_state.sales_scale = st.number_input(
            "Sales链路缩放",
            min_value=0.01,
            max_value=10.0,
            value=st.session_state.sales_scale,
            step=0.1,
            help="调整Sales链路的宽度"
        )
    
    st.markdown("---")
    st.info("💡 提示：鼠标悬停在图表上可以查看详细数据")

# ===================== 5. 数据初始化 =====================
# 确定Excel文件路径
if uploaded_file is not None:
    # 如果有上传的文件，使用上传的文件
    EXCEL_FILE_PATH = uploaded_file
    st.success(f"📂 已上传文件: {uploaded_file.name}")
else:
    # 否则使用默认文件（本地测试时）
    EXCEL_FILE_PATH = "ACC活动表现看盘2026.1.26.xlsx"

# 加载数据
try:
    sankey_data, all_nodes, original_total_incoming = read_excel_and_generate_sankey_data(EXCEL_FILE_PATH)
    df_sankey = pd.DataFrame(sankey_data, columns=["source", "target", "value", "group"])
    df_sankey["value"] = pd.to_numeric(df_sankey["value"], errors="coerce").fillna(0.0)
    
    # 显示成功消息
    st.success(f"✅ 数据加载成功：{len(df_sankey)}条记录")
    
except Exception as e:
    st.error(f"❌ 数据加载失败: {str(e)}")
    st.stop()

# ===================== 6. 数据筛选和处理（主逻辑） =====================
# 显示数据摘要
with st.expander("📊 数据摘要", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总链路数", len(df_sankey))
    with col2:
        st.metric("平台类型数", len(df_sankey["group"].unique()))
    with col3:
        total_coop = df_sankey[df_sankey["source"].str.contains("合作数量")]["value"].sum()
        st.metric("总合作数量", f"{total_coop:,.0f}")
    with col4:
        total_sales = df_sankey[df_sankey["target"] == "总sales"]["value"].sum()
        st.metric("总销售额", f"{total_sales:,.2f}")

# 数据筛选
df_filtered = df_sankey.copy()
if st.session_state.search_keyword and st.session_state.search_keyword.strip():
    kw = st.session_state.search_keyword.strip().lower()
    df_filtered = df_filtered[
        df_filtered["source"].str.lower().str.contains(kw) |
        df_filtered["target"].str.lower().str.contains(kw) |
        df_filtered["group"].str.lower().str.contains(kw)
    ]

df_agg = df_filtered.groupby(["source", "target", "group"], as_index=False)["value"].sum()
df_agg = df_agg[df_agg["value"] > 0]

# 动态识别所有平台类型
all_sources_targets = pd.concat([df_agg["source"], df_agg["target"]])
platform_nodes_set = set()
for node in all_sources_targets.unique():
    node_str = str(node)
    if (not node_str.endswith("合作数量") and
        not node_str.endswith("clicks") and
        not node_str.endswith("orders") and
        not node_str.endswith("sales") and
        node_str not in ["总数量", "总clicks", "总orders", "总sales"] and
        node_str != "nan" and node_str != ""):
        platform_nodes_set.add(node_str)

platform_nodes = sorted(list(platform_nodes_set))

# 节点排序
coop_nodes = []
click_nodes = []
order_nodes = []
sales_nodes = []
total_nodes = []

for platform in platform_nodes:
    coop_node = f"{platform}合作数量"
    if coop_node in df_agg["source"].values or coop_node in df_agg["target"].values:
        coop_nodes.append(coop_node)

    click_node = f"{platform}clicks"
    if click_node in df_agg["source"].values or click_node in df_agg["target"].values:
        click_nodes.append(click_node)

    order_node = f"{platform}orders"
    if order_node in df_agg["source"].values or order_node in df_agg["target"].values:
        order_nodes.append(order_node)

    sales_node = f"{platform}sales"
    if sales_node in df_agg["source"].values or sales_node in df_agg["target"].values:
        sales_nodes.append(sales_node)

# 总节点
for total_node in ["总数量", "总clicks", "总orders", "总sales"]:
    if total_node in df_agg["source"].values or total_node in df_agg["target"].values:
        total_nodes.append(total_node)

# 构建节点列表
all_nodes_sorted = platform_nodes + coop_nodes + ["总数量"] + click_nodes + ["总clicks"] + order_nodes + ["总orders"] + sales_nodes + ["总sales"]

# 清理节点
all_nodes_sorted = [str(node).strip() for node in all_nodes_sorted if node and str(node).strip() and str(node) != "nan"]
all_nodes_sorted = list(dict.fromkeys(all_nodes_sorted))

# 创建节点ID映射
node_id_map = {node: idx for idx, node in enumerate(all_nodes_sorted)}

# 节点统计和占比计算
original_total_node_values = {
    "总数量": original_total_incoming.get("总数量", 0),
    "总clicks": original_total_incoming.get("总clicks", 0),
    "总orders": original_total_incoming.get("总orders", 0),
    "总sales": original_total_incoming.get("总sales", 0)
}

filtered_total_incoming = df_agg.groupby("target")["value"].sum().to_dict()
filtered_total_outgoing = df_agg.groupby("source")["value"].sum().to_dict()

node_customdata = []
for node in all_nodes_sorted:
    incoming = filtered_total_incoming.get(node, 0)
    outgoing = filtered_total_outgoing.get(node, 0)

    # 计算占比（使用原始总量）
    ratio = ""
    if node == "总数量" and original_total_node_values["总数量"] > 0:
        ratio = f"总合作数量：{original_total_node_values['总数量']:.0f}"
    elif node == "总clicks" and original_total_node_values["总clicks"] > 0:
        ratio = f"总Clicks：{original_total_node_values['总clicks']:.0f}"
    elif node == "总orders" and original_total_node_values["总orders"] > 0:
        ratio = f"总Orders：{original_total_node_values['总orders']:.0f}"
    elif node == "总sales" and original_total_node_values["总sales"] > 0:
        ratio = f"总Sales：{original_total_node_values['总sales']:.0f}"
    elif "合作数量" in node and original_total_node_values["总数量"] > 0:
        ratio = f"占总数量：{(outgoing / original_total_node_values['总数量'] * 100):.2f}%"
    elif "clicks" in node and node != "总clicks" and original_total_node_values["总clicks"] > 0:
        ratio = f"占总clicks：{(outgoing / original_total_node_values['总clicks'] * 100):.2f}%"
    elif "orders" in node and node != "总orders" and original_total_node_values["总orders"] > 0:
        ratio = f"占总orders：{(outgoing / original_total_node_values['总orders'] * 100):.2f}%"
    elif "sales" in node and node != "总sales" and original_total_node_values["总sales"] > 0:
        ratio = f"占总sales：{(outgoing / original_total_node_values['总sales'] * 100):.2f}%"

    node_customdata.append((incoming, outgoing, ratio))

# 匹配搜索关键词
matched_platforms = []
if st.session_state.search_keyword and st.session_state.search_keyword.strip():
    kw = st.session_state.search_keyword.strip().lower()
    matched_platforms = [p for p in platform_nodes if kw in p.lower()]

matched_nodes = []
for platform in matched_platforms:
    matched_nodes.extend([
        platform,
        f"{platform}合作数量",
        f"{platform}clicks",
        f"{platform}orders",
        f"{platform}sales"
    ])

# 生成链路数据
link_sources = []
link_targets = []
link_values = []
link_colors = []
link_customdata = []

for _, row in df_agg.iterrows():
    source = row["source"]
    target = row["target"]
    original_val = row["value"]
    group = row["group"]

    # 检查source和target是否在node_id_map中
    source_str = str(source)
    target_str = str(target)
    if source_str not in node_id_map or target_str not in node_id_map:
        continue

    # 判断属于哪个阶段，应用对应缩放系数
    if "合作数量" in target_str or "合作数量" in source_str:
        scale_factor = st.session_state.coop_scale
    elif "clicks" in target_str or "clicks" in source_str:
        scale_factor = st.session_state.clicks_scale
    elif "orders" in target_str or "orders" in source_str:
        scale_factor = st.session_state.orders_scale
    elif "sales" in target_str or "sales" in source_str:
        scale_factor = st.session_state.sales_scale
    else:
        scale_factor = 1.0

    # 检查是否匹配搜索
    is_matched = group in matched_platforms
    final_val = original_val * scale_factor
    if not is_matched and st.session_state.search_keyword and st.session_state.search_keyword.strip():
        final_val = final_val * 0.05

    # 计算链路百分比（使用原始总流入数据）
    target_total = original_total_incoming.get(target_str, 1)
    ratio = (original_val / target_total * 100) if target_total > 0 else 0

    # 确定颜色
    if is_matched:
        final_color = GROUP_COLORS.get(group, GROUP_COLORS.get(source_str, GROUP_COLORS["默认"]))
    elif st.session_state.search_keyword and st.session_state.search_keyword.strip():
        final_color = "rgba(200, 200, 200, 0.2)"
    else:
        final_color = GROUP_COLORS.get(group, GROUP_COLORS.get(source_str, GROUP_COLORS["默认"]))

    link_sources.append(node_id_map[source_str])
    link_targets.append(node_id_map[target_str])
    link_values.append(final_val)
    link_colors.append(final_color)
    link_customdata.append([source_str, target_str, original_val, ratio])

# 节点颜色
node_color_list = []
for node in all_nodes_sorted:
    if node in matched_nodes or not st.session_state.search_keyword or not st.session_state.search_keyword.strip():
        if node in GROUP_COLORS:
            node_color = GROUP_COLORS[node]
        elif "合作数量" in node:
            platform = node.replace("合作数量", "")
            node_color = GROUP_COLORS.get(platform, GROUP_COLORS["默认"])
        elif "clicks" in node:
            node_color = GROUP_COLORS.get("总clicks", GROUP_COLORS["默认"])
        elif "orders" in node:
            node_color = GROUP_COLORS.get("总orders", GROUP_COLORS["默认"])
        elif "sales" in node:
            node_color = GROUP_COLORS.get("总sales", GROUP_COLORS["默认"])
        else:
            node_color = GROUP_COLORS.get(node, GROUP_COLORS["默认"])
    else:
        node_color = "rgba(200, 200, 200, 0.2)"
    node_color_list.append(node_color)

# ===================== 7. 绘制桑基图 =====================
fig = go.Figure(data=[go.Sankey(
    node=dict(
        pad=20,
        thickness=30,
        line=dict(color="black", width=1),
        label=all_nodes_sorted,
        color=node_color_list,
        hovertemplate="<b>%{label}</b><br>流入：%{customdata[0]:,.0f}<br>流出：%{customdata[1]:,.0f}<br>%{customdata[2]}<extra></extra>",
        customdata=node_customdata
    ),
    link=dict(
        source=link_sources,
        target=link_targets,
        value=link_values,
        color=link_colors,
        hovertemplate="<b>%{customdata[0]} → %{customdata[1]}</b><br>原始数值：%{customdata[2]:,.0f}<br>占%{customdata[1]}总流入：%{customdata[3]:.2f}%<extra></extra>",
        customdata=link_customdata
    )
)])

# 添加标题
title_text = "联盟营销平台转化链路"
if st.session_state.search_keyword and st.session_state.search_keyword.strip():
    title_text += f" | 搜索：{st.session_state.search_keyword}"

fig.update_layout(
    title_text=title_text,
    font_size=12,
    autosize=True,
    font_color="pink",
    margin=dict(l=20, r=20, t=50, b=20),
    font=dict(family="Microsoft YaHei"),
    height=800
)

# 显示图表 - 修复API弃用警告
st.plotly_chart(fig, use_container_width=True, height=800)

# ===================== 8. 数据显示区域 =====================
with st.expander("📋 查看详细数据"):
    tab1, tab2, tab3 = st.tabs(["原始数据", "汇总数据", "平台统计"])
    
    with tab1:
        st.dataframe(df_sankey.head(100))
    
    with tab2:
        # 按平台汇总
        platform_summary = df_sankey.groupby("group").agg({
            "value": ["sum", "count"]
        }).round(2)
        platform_summary.columns = ["总数值", "链路数量"]
        st.dataframe(platform_summary)
    
    with tab3:
        # 平台类型统计
        st.write(f"**平台类型总数:** {len(platform_nodes)}")
        st.write(f"**匹配的平台类型:** {len(matched_platforms)}")
        
        if platform_nodes:
            st.write("**所有平台类型:**")
            cols = st.columns(3)
            for i, platform in enumerate(platform_nodes):
                with cols[i % 3]:
                    st.write(f"• {platform}")

# ===================== 9. 页脚信息 =====================
st.markdown("---")
st.caption(f"📅 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("💡 提示：修改Excel文件后，重新上传即可更新图表")

# ===================== 10. 正确运行方式 =====================
# 不要在IDE中直接运行这个文件
# 使用命令行：streamlit run sankeyyingxiao_streamlit.py