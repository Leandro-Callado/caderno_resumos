# 🧾 Gerador Automático de Caderno de Resumos 

Este projeto em **Python** gera automaticamente um **Caderno de Resumos completo em PDF**, a partir de múltiplos arquivos `.pdf` contendo resumos individuais.

O resultado final é um documento formatado no **estilo do "Caderno de Resumos do GEL"**, com:
- capa automática,
- sumário gerado dinamicamente,
- seções por eixo temático,
- formatação idêntica à do modelo original (título centralizado, autores em itálico e texto justificado).

---

## 📁 Estrutura do Projeto
```
caderno_resumos/
│
├── main.py # Código principal
├── config.json # Configurações de evento e layout
│
├── dados/
│ └── resumos/ # Coloque aqui os PDFs de entrada
│ ├── resumo1.pdf
│ ├── resumo2.pdf
│ └── ...
│
└── saida/
└── caderno_final.pdf # PDF final gerado automaticamente
```

---

## ⚙️ Instalação

### 1. Clone ou baixe o projeto
```bash
git clone https://github.com/Leandro-Callado/caderno_resumo.git
cd caderno_resumos

2. Crie um ambiente virtual
python -m venv .venv

Ative o ambiente:

Windows
.venv\Scripts\activate

Linux/macOS
source .venv/bin/activate

3. Instale as dependências
Copiar código
pip install --upgrade pip
pip install reportlab pdfplumber
```
📘 Como usar
1. Adicione os resumos

Coloque todos os arquivos .pdf de resumos individuais dentro da pasta:

`dados/resumos/`

Cada PDF deve conter o texto corrido do resumo.
O script vai tentar identificar automaticamente o título, autores, eixo temático e o texto principal.

2. Gere o caderno
Rode o script principal:
```python
python main.py
```
