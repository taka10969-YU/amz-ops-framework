"""Main Streamlit app entry - Overview page"""
import streamlit as st
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_layer.file_importer import FileImporter
from src.data_layer.data_store import DataStore

st.set_page_config(page_title="AMZ竞品运营自动化", layout="wide")
st.title("AMZ竞品运营自动化框架")

with st.sidebar:
    st.header("数据导入")
    data_dir = st.text_input("数据目录路径", value="")
    if st.button("导入数据") and data_dir:
        with st.spinner("正在导入数据..."):
            importer = FileImporter()
            results = importer.import_directory(data_dir)
            st.session_state["imported"] = results

            store = DataStore()
            for r in results:
                fmt = r.get("format", "unknown")
                fname = r.get("filename", "unknown")
                store.save_json(r, f"import_{fmt}_{fname}.json", subdir="raw")

            st.success(f"导入 {len(results)} 个文件")

    st.divider()
    if st.button("清除所有数据"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("已清除")

if "imported" in st.session_state:
    results = st.session_state["imported"]

    fmt_counter = Counter(r.get("format", "unknown") for r in results)
    total_records = 0
    for r in results:
        data = r.get("data")
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    total_records += len(v)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("导入文件数", len(results))
    with col2:
        st.metric("数据格式类型", len(fmt_counter))
    with col3:
        st.metric("总记录数", total_records)

    st.subheader("文件格式分布")
    fmt_df_data = [{"格式": fmt, "数量": count} for fmt, count in fmt_counter.most_common()]
    if fmt_df_data:
        st.dataframe(fmt_df_data, use_container_width=True, hide_index=True)

    st.subheader("文件详情")
    for r in results:
        fmt = r.get("format", "unknown")
        fname = r.get("filename", "")
        path = r.get("path", "")
        data = r.get("data")
        record_count = 0
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    record_count += len(v)

        with st.expander(f"[{fmt}] {fname}"):
            st.write(f"路径: {path}")
            st.write(f"记录数: {record_count}")
            if isinstance(data, dict):
                keys = [k for k in data.keys() if k != "dataframe"]
                st.write(f"数据键: {', '.join(keys)}")
            if "error" in r:
                st.error(f"错误: {r['error']}")
else:
    st.info("请在左侧导入数据目录开始使用")
