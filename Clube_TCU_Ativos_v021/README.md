
# Clube TCU Ativos — Streamlit v0.2

Esta versão recebe diretamente um TXT bruto copiado da listagem de atividades.

## Fluxo

Strava (copiar) → TXT bruto → upload no Streamlit → parser → cruzamento com equipes → pontuação → painel.

## Arquivos

- `app.py` — aplicação Streamlit.
- `equipes.csv` — cadastro permanente atleta/equipe.
- `requirements.txt` — dependências.

## Como executar

No Prompt/PowerShell, dentro desta pasta:

```bash
streamlit run app.py
```

## Uso diário

1. Copie a listagem de atividades.
2. Cole no Bloco de Notas e salve como `.txt`.
3. Abra o painel.
4. Faça upload do TXT.
5. Confira a **Data de referência do TXT**. Ela é usada para interpretar “Hoje” e “Ontem”.
6. O painel atualiza a apuração automaticamente.

## Dados extraídos

- NOME_ATLETA
- DATA
- ATIVIDADE
- DURACAO

A EQUIPE vem do arquivo permanente `equipes.csv`.

## Regra da equipe

- 1 atleta ativo em um dia = 1 ponto-base.
- Várias atividades do mesmo atleta no mesmo dia continuam valendo 1 ponto-base.
- Bônus de engajamento:
  - abaixo de 50%: +0
  - 50% a 69,99%: +1
  - 70% a 89,99%: +2
  - 90% a 99,99%: +3
  - 100%: +5

## Observação

O parser aceita as formas encontradas no TXT de teste, incluindo:
- português e inglês;
- “Hoje” e “Ontem”;
- datas como “5 de setembro de 2026”;
- datas como “September 4, 2026”;
- duração como `48min 40s`, `1h 9min`, `46m 32s` e `1h 0m`.

Comentários sem uma linha válida de data/hora e sem duração não são tratados como atividades.


## GitHub

Estrutura sugerida: `Dornelesjc/Semana_Integracao/Clube_TCU_Ativos_v021`.

O arquivo `.gitignore` impede o envio da pasta `teste_local/`, de TXT brutos,
arquivos gerados localmente e segredos. Mantenha o `.gitignore` antes do
primeiro commit com dados reais.
