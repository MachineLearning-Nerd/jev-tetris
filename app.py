from __future__ import annotations

import streamlit as st

from tetris_game import render_tetris_app


st.set_page_config(
    page_title="Jev Plays Tetris",
    page_icon="🧱",
    layout="wide",
)


def main() -> None:
    render_tetris_app()


if __name__ == "__main__":
    main()
