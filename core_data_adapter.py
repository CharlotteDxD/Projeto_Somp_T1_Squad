"""
==============================================================================
SOMPO PREDICT v15 - DATA ADAPTER (FRENTE 4)
==============================================================================
Owner:     Charles
Tipo:      Modulo transversal de carregamento de dados

Objetivo:
    Fornecer um carregador unico que tenta arquivo REAL primeiro
    e cai em MOCK automaticamente caso o arquivo nao exista.

    Isso permite que cada membro do squad simplesmente coloque o
    arquivo dele na pasta data/ sem precisar editar codigo Python.

Estrutura esperada da pasta:
    sompo_predict/
    ├── app.py
    ├── pagina_*.py
    └── data/
        ├── susep_real.xlsx       <- Guilherme coloca aqui
        ├── telemetria_esp32.csv  <- Anthony coloca aqui
        ├── frota_real.csv        <- Gustavo (opcional)
        └── modelo_xgboost.pkl    <- Guilherme/Gustavo (opcional)

Uso:
    from core_data_adapter import carregar_dataset, status_dados

    df, fonte = carregar_dataset(
        caminho="data/susep_real.xlsx",
        gerador_mock=_meu_mock,
    )
    # fonte = "REAL" ou "MOCK"

    # Para mostrar badge na UI:
    status_dados("data/susep_real.xlsx")  # renderiza pill verde/amarela
==============================================================================
"""
from pathlib import Path
from typing import Callable, Tuple, Optional, Any
import pandas as pd
import streamlit as st


# ==========================================================================
# CAMINHOS PADRAO DOS ARQUIVOS DO SQUAD
# ==========================================================================
DATA_DIR = Path("data")

ARQUIVOS_ESPERADOS = {
    # Guilherme - Data Science (#F5A623)
    "susep_real":      {"path": DATA_DIR / "susep_real.xlsx",
                        "owner": "Guilherme",
                        "descricao": "Base SUSEP de seguros rurais (100+ apolices)"},
    # Anthony - IoT (#A855F7)
    "telemetria_esp32": {"path": DATA_DIR / "telemetria_esp32.csv",
                         "owner": "Anthony",
                         "descricao": "Leituras do ESP32 via Wokwi (200+ linhas)"},
    # Gustavo - Cloud (#FF4D6A)
    "frota_real":      {"path": DATA_DIR / "frota_real.csv",
                        "owner": "Gustavo",
                        "descricao": "Frota completa com IDs reais da Sompo"},
    # Modelos treinados
    "modelo_xgboost":  {"path": DATA_DIR / "modelo_xgboost.pkl",
                        "owner": "Guilherme",
                        "descricao": "XGBoost serializado treinado em base real"},
    "modelo_lstm":     {"path": DATA_DIR / "modelo_lstm.h5",
                        "owner": "Gustavo",
                        "descricao": "LSTM treinado para series temporais"},
}


# ==========================================================================
# CARREGADOR PRINCIPAL
# ==========================================================================

def carregar_dataset(
    caminho: str | Path,
    gerador_mock: Callable[[], pd.DataFrame],
    tipo: str = "auto",
) -> Tuple[pd.DataFrame, str]:
    """
    Tenta carregar arquivo real. Se nao existir, retorna o mock.

    Args:
        caminho: caminho do arquivo (absoluto ou relativo)
        gerador_mock: funcao que retorna DataFrame fake
        tipo: 'auto' (detecta extensao), 'csv', 'xlsx', 'parquet'

    Returns:
        (DataFrame, fonte) onde fonte = "REAL" ou "MOCK"
    """
    p = Path(caminho)

    if not p.exists():
        return gerador_mock(), "MOCK"

    try:
        ext = p.suffix.lower() if tipo == "auto" else f".{tipo}"

        if ext == ".csv":
            df = pd.read_csv(p)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(p)
        elif ext == ".parquet":
            df = pd.read_parquet(p)
        elif ext == ".json":
            df = pd.read_json(p)
        else:
            return gerador_mock(), "MOCK"

        return df, "REAL"

    except Exception as e:
        # Em caso de erro de leitura, registra warning mas nao quebra
        st.warning(f"Erro ao ler {p.name}: {e}. Usando mock.")
        return gerador_mock(), "MOCK"


def carregar_arquivo_binario(caminho: str | Path) -> Optional[Any]:
    """
    Carrega arquivos binarios (modelos .pkl, .h5).
    Retorna None se nao existir.
    """
    import pickle
    p = Path(caminho)
    if not p.exists():
        return None
    try:
        with open(p, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


# ==========================================================================
# UI HELPERS - badge de status na pagina
# ==========================================================================

def status_dados(chave_arquivo: str, label: str = "") -> None:
    """
    Renderiza um badge no Streamlit indicando se o dado e REAL ou MOCK.

    Args:
        chave_arquivo: chave em ARQUIVOS_ESPERADOS (ex: "susep_real")
        label: texto opcional para sobrescrever a descricao padrao
    """
    if chave_arquivo not in ARQUIVOS_ESPERADOS:
        return

    info = ARQUIVOS_ESPERADOS[chave_arquivo]
    real = info["path"].exists()

    cor   = "#22D48A" if real else "#F5A623"
    label_real = "DADOS REAIS" if real else "MOCK (aguardando entrega)"
    desc  = label or info["descricao"]

    st.markdown(f"""
    <div style="display:inline-flex;gap:8px;align-items:center;
                background:{cor}10;border:1px solid {cor}40;
                border-radius:6px;padding:4px 12px;margin-bottom:1rem;
                font-size:0.78rem;">
        <span style="color:{cor};font-weight:700;letter-spacing:0.05em;">●</span>
        <span style="color:{cor};font-weight:600;">{label_real}</span>
        <span style="color:#8B8FA8;">·</span>
        <span style="color:#8B8FA8;">{desc}</span>
        <span style="color:#4A4D62;font-size:0.7rem;">({info['owner']})</span>
    </div>
    """, unsafe_allow_html=True)


def painel_status_geral() -> None:
    """
    Renderiza um painel completo com status de todos os arquivos esperados.
    Usado na tela 'Sobre o Projeto' e no debug.
    """
    cores_membro = {
        "Guilherme": "#F5A623",
        "Gustavo":   "#FF4D6A",
        "Anthony":   "#A855F7",
        "Rafael":    "#5B7FFF",
        "Charles":   "#22D48A",
    }

    st.markdown("##### Status dos arquivos esperados do squad")
    st.caption("Cada membro coloca seu arquivo na pasta `data/` para o sistema "
               "automaticamente trocar de MOCK para REAL.")

    n_real = sum(1 for k, v in ARQUIVOS_ESPERADOS.items() if v["path"].exists())
    n_total = len(ARQUIVOS_ESPERADOS)
    pct = round(100 * n_real / n_total)

    cor_progress = "#22D48A" if pct >= 80 else "#F5A623" if pct >= 40 else "#FF4D6A"
    st.markdown(f"""
    <div style="background:#0D0F18;border:1px solid {cor_progress}33;
                border-radius:10px;padding:14px 18px;margin-bottom:1rem;">
        <div style="display:flex;justify-content:space-between;
                    align-items:center;margin-bottom:8px;">
            <span style="font-size:0.85rem;color:#EEF0F8;font-weight:600;">
                Integracao com dados reais</span>
            <span style="font-size:1.2rem;font-weight:800;color:{cor_progress};">
                {n_real}/{n_total}</span>
        </div>
        <div style="background:#07080C;height:6px;border-radius:3px;overflow:hidden;">
            <div style="background:{cor_progress};width:{pct}%;height:100%;
                        border-radius:3px;"></div>
        </div>
        <div style="font-size:0.7rem;color:#8B8FA8;margin-top:6px;text-align:right;">
            {pct}% migrado para dados reais</div>
    </div>
    """, unsafe_allow_html=True)

    for chave, info in ARQUIVOS_ESPERADOS.items():
        existe = info["path"].exists()
        cor = "#22D48A" if existe else "#F5A623"
        cor_owner = cores_membro.get(info["owner"], "#8B8FA8")
        status_text = "REAL" if existe else "MOCK"
        tamanho = ""
        if existe:
            try:
                size_kb = info["path"].stat().st_size / 1024
                tamanho = f" · {size_kb:.0f} KB"
            except Exception:
                pass

        st.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-left:3px solid {cor};border-radius:8px;
                    padding:10px 16px;margin-bottom:6px;
                    display:flex;justify-content:space-between;align-items:center;">
            <div>
                <div style="display:flex;gap:8px;align-items:center;
                            margin-bottom:3px;">
                    <code style="font-size:0.8rem;color:#EEF0F8;
                                 background:#131520;padding:2px 6px;
                                 border-radius:4px;">{info['path']}</code>
                    <span style="font-size:0.65rem;color:{cor_owner};
                                 background:{cor_owner}20;padding:2px 7px;
                                 border-radius:4px;font-weight:700;">
                        {info['owner']}</span>
                </div>
                <div style="font-size:0.72rem;color:#8B8FA8;">
                    {info['descricao']}</div>
            </div>
            <span style="font-size:0.7rem;font-weight:700;color:{cor};
                         background:{cor}18;padding:3px 10px;border-radius:5px;
                         white-space:nowrap;">{status_text}{tamanho}</span>
        </div>
        """, unsafe_allow_html=True)


def garantir_pasta_data() -> None:
    """Cria a pasta data/ se nao existir. Chamado no boot do app."""
    DATA_DIR.mkdir(exist_ok=True)
    # Cria README explicativo
    readme = DATA_DIR / "README.md"
    if not readme.exists():
        conteudo = """# Pasta de Dados - Sompo Predict

Esta pasta recebe os arquivos REAIS que substituem os mocks automaticamente.

## Arquivos esperados

| Arquivo                   | Owner     | Descricao                              |
|---------------------------|-----------|----------------------------------------|
| `susep_real.xlsx`         | Guilherme | Base SUSEP rural com 100+ apolices     |
| `telemetria_esp32.csv`    | Anthony   | Leituras do ESP32 via Wokwi            |
| `frota_real.csv`          | Gustavo   | Frota com IDs reais da Sompo           |
| `modelo_xgboost.pkl`      | Guilherme | XGBoost serializado                    |
| `modelo_lstm.h5`          | Gustavo   | LSTM para series temporais             |

## Como funciona

Cada pagina do menu chama `carregar_dataset(caminho, gerador_mock)`.
Se o arquivo existe, usa ele. Se nao, cai no mock automaticamente.
Sem precisar editar codigo Python.
"""
        readme.write_text(conteudo, encoding="utf-8")
