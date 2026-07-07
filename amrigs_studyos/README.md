# AMRIGS StudyOS

Aplicativo desktop local para planejamento de 20 semanas, sessões de estudo, revisões espaçadas, banco de erros, telemetria e backup portátil.

## Estado da versão 0.1.0

A versão inicial já contém:

- banco SQLite local, sem servidor e sem login;
- mapa de conteúdos por áreas, blocos, macrofamílias e linhas individuais;
- cronograma inicial de 20 semanas, com dois blocos de segunda a sexta e sábado flexível;
- Pediatria em dois contatos semanais;
- fases de cobertura, consolidação, integração por questões e revisão final;
- sessões planejadas e sessões livres;
- cronômetro, tempo estimado e tempo real;
- marcação individual de conteúdo como pendente, parcial ou concluído;
- questões, acertos, foco, uso do tempo, dificuldade e resultado percebido;
- revisões D+1, D+7 e D+21 geradas a partir da data real de conclusão;
- dashboard, banco de erros, telemetria e prioridades operacionais;
- tema claro/escuro, cor de destaque e densidade visual;
- backup automático e exportação/importação `.amrigs-save`.

## Instalação no Windows

1. Instale Python 3.11 ou 3.12.
2. Execute `install_windows.bat`.
3. Execute `run_windows.bat`.

Alternativamente, no terminal:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python run.py
```

## Dados locais

O banco e os backups ficam em:

```text
%APPDATA%\AMRIGS StudyOS
```

É possível alterar o diretório com a variável de ambiente `AMRIGS_STUDYOS_HOME`.

## Save portátil

Em **Configurações > Backup e migração**:

- `Exportar .amrigs-save` cria um pacote com banco, manifesto, versão e checksum;
- `Importar save` valida integridade, salva o estado atual e prepara a restauração;
- a restauração é aplicada na inicialização seguinte.

## Gerar executável

Execute `build_windows.bat`. O executável será criado em `dist\AMRIGS_StudyOS`.

## Observações da primeira versão

- O replanejamento automático ainda é conservador: o aplicativo calcula prioridade operacional e preserva o histórico, mas não movimenta silenciosamente as sessões.
- O cronograma pode ser regenerado sem apagar sessões reais, erros ou progresso dos conteúdos.
- A distribuição inicial é uma base editável; as próximas versões incluirão editor visual de sessões, fila de propostas de replanejamento e relatórios gráficos mais avançados.
