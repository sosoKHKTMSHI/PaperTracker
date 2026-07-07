from __future__ import annotations

from typing import Iterable

from .db import Database


def _items(spec: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for chunk in spec.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        title, ip = chunk.rsplit("|", 1)
        out.append((title.strip(), int(ip)))
    return out


def M(code: str, name: str, minutes: int, spec: str) -> dict:
    items = _items(spec)
    return {
        "code": code,
        "name": name,
        "minutes": minutes,
        "priority": max(ip for _, ip in items),
        "items": items,
    }


CATALOG: list[dict] = [
    {
        "code": "CLI", "name": "Clínica Médica", "color": "#7C3AED",
        "blocks": [
            {"code": "CLI-01", "name": "Cardiologia", "weight": 19, "families": [
                M("CLI-CAR-01", "Síndrome coronariana aguda", 90, "Abordagem integrada|10; Infarto com supradesnivelamento de ST|10; Infarto sem supradesnivelamento e angina instável|9"),
                M("CLI-CAR-02", "Insuficiência cardíaca", 80, "Insuficiência cardíaca crônica|10; Insuficiência cardíaca aguda|9"),
                M("CLI-CAR-03", "Hipertensão arterial", 70, "Hipertensão arterial sistêmica|10; Crises hipertensivas|9"),
                M("CLI-CAR-04", "ECG, fibrilação atrial e anticoagulação", 90, "Interpretação de ECG|10; Fibrilação atrial|10; Anticoagulação|8; Síncope|7"),
                M("CLI-CAR-05", "ACLS e arritmias", 95, "Parada cardiorrespiratória e ACLS|10; Taquicardias supraventriculares|8; Taquicardia ventricular e ritmos de QRS largo|8; Bradiarritmias e bloqueios atrioventriculares|8"),
                M("CLI-CAR-06", "Valvopatias e endocardite", 75, "Valvopatias|8; Endocardite infecciosa|8; Hipertensão pulmonar|5"),
                M("CLI-CAR-07", "Pericárdio e miocárdio", 60, "Pericardite e tamponamento cardíaco|7; Cardiomiopatias|6; Miocardite|6"),
                M("CLI-CAR-08", "Síndromes vasculares", 65, "Dissecção aguda de aorta|7; Trombose venosa profunda|7; Doença arterial periférica|6"),
            ]},
            {"code": "CLI-02", "name": "Pneumologia e terapia intensiva", "weight": 14, "families": [
                M("CLI-PNE-01", "Asma e DPOC", 95, "Asma|10; DPOC|10; Espirometria|8"),
                M("CLI-PNE-02", "Infecções respiratórias", 95, "Pneumonia adquirida na comunidade|10; Tuberculose pulmonar|10; Pneumonia hospitalar e associada à ventilação|8"),
                M("CLI-PNE-03", "Tromboembolismo e circulação pulmonar", 75, "Tromboembolismo pulmonar|10; Hemoptise|6; Hipertensão pulmonar|5"),
                M("CLI-PNE-04", "Gasometria e insuficiência respiratória", 90, "Gasometria arterial|10; Insuficiência respiratória aguda|9; Oxigenoterapia|8; Ventilação não invasiva|8"),
                M("CLI-PNE-05", "Ventilação invasiva e SDRA", 80, "Ventilação mecânica invasiva|9; Síndrome do desconforto respiratório agudo|8"),
                M("CLI-PNE-06", "Síndromes pleurais", 65, "Derrame pleural|8; Pneumotórax|8"),
                M("CLI-PNE-07", "Pneumologia crônica complementar", 55, "Doenças pulmonares intersticiais|6; Apneia obstrutiva do sono|6; Doenças pulmonares ocupacionais|4"),
            ]},
            {"code": "CLI-03", "name": "Endocrinologia e metabolismo", "weight": 12, "families": [
                M("CLI-END-01", "Diabetes ambulatorial", 100, "Diagnóstico e classificação do diabetes|10; Tratamento do diabetes tipo 2|10; Insulinoterapia|9; Complicações crônicas do diabetes|9"),
                M("CLI-END-02", "Emergências diabéticas", 85, "Cetoacidose diabética|10; Estado hiperosmolar hiperglicêmico|9; Hipoglicemia|9"),
                M("CLI-END-03", "Risco cardiometabólico", 65, "Dislipidemia|9; Obesidade|8; Síndrome metabólica|6"),
                M("CLI-END-04", "Função tireoidiana e emergências", 80, "Hipotireoidismo|9; Hipertireoidismo e tireotoxicose|8; Tempestade tireotóxica e coma mixedematoso|7"),
                M("CLI-END-05", "Doença estrutural da tireoide", 65, "Nódulo tireoidiano|8; Tireoidites|6; Câncer de tireoide|6"),
                M("CLI-END-06", "Cálcio e paratireoide", 65, "Hipercalcemia|8; Hipocalcemia|7; Hiperparatireoidismo|6"),
                M("CLI-END-07", "Doenças adrenais", 65, "Insuficiência adrenal e crise adrenal|7; Síndrome de Cushing|5; Feocromocitoma|5"),
            ]},
            {"code": "CLI-04", "name": "Nefrologia, eletrólitos e ácido-base", "weight": 12, "families": [
                M("CLI-NEF-01", "Lesão renal aguda e diálise", 85, "Lesão renal aguda|10; Indicações de terapia renal substitutiva|9"),
                M("CLI-NEF-02", "Doença renal crônica", 75, "Doença renal crônica|10; Doença renal diabética|8"),
                M("CLI-NEF-03", "Sódio e potássio", 100, "Hiponatremia|10; Hipernatremia|8; Hipercalemia|10; Hipocalemia|9"),
                M("CLI-NEF-04", "Distúrbios ácido-base", 110, "Acidose metabólica|10; Alcalose metabólica|9; Distúrbios ácido-base mistos|9; Acidose respiratória|8; Alcalose respiratória|8"),
                M("CLI-NEF-05", "Síndromes glomerulares", 75, "Síndrome nefrítica|8; Síndrome nefrótica|8; Glomerulonefrite rapidamente progressiva|6"),
                M("CLI-NEF-06", "Trato urinário e minerais", 70, "Infecção urinária e pielonefrite|8; Nefrolitíase|7; Distúrbios do magnésio|6; Distúrbios do fósforo|5"),
            ]},
            {"code": "CLI-05", "name": "Gastroenterologia e hepatologia", "weight": 11, "families": [
                M("CLI-GAS-01", "Hemorragia digestiva alta e úlcera", 85, "Hemorragia digestiva alta|10; Doença ulcerosa péptica|8"),
                M("CLI-GAS-02", "Cirrose e hipertensão portal I", 90, "Cirrose hepática|10; Ascite e peritonite bacteriana espontânea|10"),
                M("CLI-GAS-03", "Cirrose descompensada II", 85, "Encefalopatia hepática|9; Hemorragia varicosa|9; Síndrome hepatorrenal|8"),
                M("CLI-GAS-04", "Pancreatites", 75, "Pancreatite aguda|10; Pancreatite crônica|6"),
                M("CLI-GAS-05", "Síndromes intestinais agudas", 65, "Hemorragia digestiva baixa|8; Diarreia aguda|8"),
                M("CLI-GAS-06", "Hepatites e insuficiência hepática", 70, "Hepatites virais|8; Insuficiência hepática aguda|7"),
                M("CLI-GAS-07", "Doenças digestivas crônicas estruturais", 65, "Doença do refluxo gastroesofágico|7; Doença inflamatória intestinal|7"),
                M("CLI-GAS-08", "Diarreia crônica e doenças funcionais", 65, "Diarreia crônica|6; Doença celíaca|6; Síndrome do intestino irritável|5; Constipação|5"),
            ]},
            {"code": "CLI-06", "name": "Infectologia", "weight": 12, "families": [
                M("CLI-INF-01", "Sepse e antibioticoterapia", 100, "Sepse e choque séptico|10; Antibioticoterapia empírica|10; Infecção relacionada à assistência|7"),
                M("CLI-INF-02", "Tuberculose e hanseníase", 80, "Tuberculose|10; Hanseníase|7"),
                M("CLI-INF-03", "HIV", 85, "Diagnóstico e tratamento inicial do HIV|9; Infecções oportunistas no HIV|9"),
                M("CLI-INF-04", "IST e profilaxias", 80, "Sífilis|9; Infecções sexualmente transmissíveis|8; Profilaxia pós-exposição|8"),
                M("CLI-INF-05", "Infecções invasivas", 80, "Meningites|9; Endocardite infecciosa|8"),
                M("CLI-INF-06", "Dengue", 60, "Dengue|9"),
                M("CLI-INF-07", "Zoonoses e arboviroses", 65, "Leptospirose|8; Chikungunya, Zika e febre amarela|5"),
                M("CLI-INF-08", "Hepatites e sorologias", 60, "Hepatites virais e sorologias|8"),
                M("CLI-INF-09", "Vacinação e vírus respiratórios", 70, "Vacinação do adulto e imunossuprimido|8; Influenza|7; COVID-19|6"),
            ]},
            {"code": "CLI-07", "name": "Neurologia", "weight": 8, "families": [
                M("CLI-NEU-01", "AVC isquêmico", 85, "Acidente vascular cerebral isquêmico|10; Ataque isquêmico transitório|8"),
                M("CLI-NEU-02", "Hemorragia intracraniana", 65, "Hemorragia intracraniana|9"),
                M("CLI-NEU-03", "Epilepsia e estado de mal", 75, "Estado de mal epiléptico|9; Epilepsia|8"),
                M("CLI-NEU-04", "Delirium e demências", 70, "Delirium|9; Demências|8"),
                M("CLI-NEU-05", "Neuroinfecção e cefaleia", 70, "Meningite e encefalite|9; Cefaleias e sinais de alarme|8"),
                M("CLI-NEU-06", "Movimento e equilíbrio", 60, "Doença de Parkinson|7; Vertigem central e periférica|7"),
                M("CLI-NEU-07", "Neurologia neuromuscular e especial", 70, "Miastenia gravis|7; Síndrome de Guillain-Barré|6; Esclerose múltipla|5; Morte encefálica|7"),
            ]},
            {"code": "CLI-08", "name": "Hematologia, reumatologia, geriatria e complementares", "weight": 12, "families": [
                M("CLI-HEM-01", "Anemias", 85, "Anemia ferropriva|9; Anemia megaloblástica|7; Anemias hemolíticas|7; Anemia da doença crônica|6"),
                M("CLI-HEM-02", "Transfusão e hemostasia", 85, "Transfusão de hemocomponentes|9; Coagulação intravascular disseminada|8; Púrpura trombocitopênica imune|7; Hemofilia e coagulopatias|6"),
                M("CLI-HEM-03", "Neoplasias hematológicas", 65, "Leucemias|7; Linfomas|7; Mieloma múltiplo|6"),
                M("CLI-REU-01", "Reumatologia inflamatória", 75, "Artrite reumatoide|8; Lúpus eritematoso sistêmico|8; Vasculites|6; Espondiloartrites|6"),
                M("CLI-REU-02", "Artropatias e dor crônica", 60, "Gota e artrites por cristais|8; Osteoartrite|7; Fibromialgia|5"),
                M("CLI-GER-01", "Geriatria e cuidados paliativos", 80, "Avaliação geriátrica ampla|8; Quedas e fragilidade|8; Polifarmácia e desprescrição|7; Cuidados paliativos|8"),
                M("CLI-DER-01", "Alergia e pele", 75, "Anafilaxia|9; Urticária e angioedema|6; Erisipela e celulite|7; Farmacodermias graves|7"),
                M("CLI-TOX-01", "Toxicologia e envenenamentos", 70, "Intoxicação por paracetamol|7; Intoxicação por opioides|7; Organofosforados|6; Acidentes por animais peçonhentos|7"),
            ]},
        ],
    },
    {
        "code": "CIR", "name": "Cirurgia", "color": "#EF4444",
        "blocks": [
            {"code": "CIR-01", "name": "Trauma e queimaduras", "weight": 22, "families": [
                M("CIR-TRA-01", "Atendimento inicial e via aérea", 90, "Atendimento inicial ao politraumatizado|10; Via aérea no trauma|10"),
                M("CIR-TRA-02", "Choque e controle de danos", 90, "Choque hemorrágico|10; Transfusão maciça|9; Controle de danos|8"),
                M("CIR-TRA-03", "Trauma torácico", 100, "Trauma torácico|10; Pneumotórax hipertensivo|10; Hemotórax maciço|9; Tamponamento cardíaco traumático|9"),
                M("CIR-TRA-04", "Trauma abdominal", 100, "Trauma abdominal fechado|10; FAST e eFAST|9; Trauma abdominal penetrante|9; Trauma hepático e esplênico|8"),
                M("CIR-TRA-05", "Neurotrauma e coluna", 90, "Trauma cranioencefálico|10; Trauma raquimedular|8; Trauma cervical|7"),
                M("CIR-TRA-06", "Trauma pélvico e extremidades", 70, "Trauma pélvico|8; Trauma de extremidades|8"),
                M("CIR-TRA-07", "Queimaduras", 90, "Queimaduras|10; Reposição volêmica no queimado|9; Lesão inalatória|8"),
                M("CIR-TRA-08", "Situações especiais no trauma", 60, "Trauma urológico|7; Afogamento e hipotermia|6; Trauma na gestante|6"),
            ]},
            {"code": "CIR-02", "name": "Abdome agudo", "weight": 18, "families": [
                M("CIR-ABD-01", "Abdome inflamatório", 80, "Apendicite aguda|10; Abdome agudo inflamatório|8"),
                M("CIR-ABD-02", "Obstrução intestinal", 90, "Obstrução intestinal|10; Abdome agudo obstrutivo|9; Volvo de sigmoide e ceco|8; Íleo paralítico|7"),
                M("CIR-ABD-03", "Perfuração e peritonite", 85, "Perfuração de víscera oca|10; Peritonite|9; Abdome agudo perfurativo|9"),
                M("CIR-ABD-04", "Abdome vascular", 75, "Isquemia mesentérica|9; Abdome agudo vascular|8"),
                M("CIR-ABD-05", "Cólon grave e compartimento", 65, "Diverticulite aguda|9; Megacólon tóxico|7; Síndrome compartimental abdominal|6"),
            ]},
            {"code": "CIR-03", "name": "Hepatobiliar, pâncreas e trato digestivo alto", "weight": 14, "families": [
                M("CIR-HPB-01", "Vesícula biliar", 75, "Colelitíase|9; Colecistite aguda|10"),
                M("CIR-HPB-02", "Via biliar", 80, "Coledocolitíase|9; Colangite aguda|10; Icterícia obstrutiva|8"),
                M("CIR-PAN-01", "Pancreatite aguda", 80, "Pancreatite aguda|10; Pancreatite biliar|9"),
                M("CIR-PAN-02", "Pâncreas crônico e complicado", 65, "Pseudocisto e necrose pancreática|7; Pancreatite crônica|6; Câncer de pâncreas|7"),
                M("CIR-TDA-01", "Trato digestivo alto benigno", 65, "Doença ulcerosa péptica complicada|8; Doença do refluxo e hérnia hiatal|6"),
                M("CIR-TDA-02", "Neoplasias digestivas altas e hepatobiliares", 70, "Câncer gástrico|8; Câncer de esôfago|6; Tumores hepáticos|6; Tumores periampulares|5"),
            ]},
            {"code": "CIR-04", "name": "Perioperatório, infecção e paciente crítico", "weight": 14, "families": [
                M("CIR-PER-01", "Avaliação e preparo pré-operatório", 90, "Avaliação pré-operatória|10; Risco cardiovascular perioperatório|9; Manejo perioperatório de medicamentos|8; Jejum e preparo pré-operatório|7"),
                M("CIR-PER-02", "Profilaxias cirúrgicas", 75, "Profilaxia de tromboembolismo venoso|10; Antibioticoprofilaxia cirúrgica|10"),
                M("CIR-PER-03", "Complicações e infecção do sítio", 85, "Complicações pós-operatórias|10; Infecção do sítio cirúrgico|9"),
                M("CIR-PER-04", "Sepse e infecções graves", 85, "Sepse de origem cirúrgica|10; Fasceíte necrosante|9; Gangrena de Fournier|8"),
                M("CIR-PER-05", "Fluidos, transfusão e acessos", 75, "Reposição volêmica|9; Hemotransfusão|9; Acessos vasculares|7"),
                M("CIR-PER-06", "Falhas de parede e fístulas", 70, "Deiscência e evisceração|8; Fístulas digestivas|8"),
                M("CIR-PER-07", "Recuperação e dispositivos", 70, "Cicatrização|8; Nutrição no paciente cirúrgico|8; Drenos e sondas|7; Síndrome compartimental|8"),
            ]},
            {"code": "CIR-05", "name": "Hérnias e coloproctologia", "weight": 12, "families": [
                M("CIR-HER-01", "Hérnias inguinais e femorais", 80, "Hérnia inguinal|10; Hérnia encarcerada e estrangulada|10; Hérnia femoral|8"),
                M("CIR-HER-02", "Outras hérnias da parede", 55, "Hérnia incisional|8; Hérnia umbilical|7"),
                M("CIR-COL-01", "Neoplasia colorretal", 85, "Câncer colorretal|10; Pólipos colorretais|8; Síndromes hereditárias colorretais|6"),
                M("CIR-COL-02", "Cólon inflamatório e ostomias", 65, "Doença diverticular|9; Doença inflamatória intestinal cirúrgica|6; Ostomias|6"),
                M("CIR-ANO-01", "Doenças anorretais", 75, "Doença hemorroidária|8; Fissura anal|8; Abscesso anorretal|8; Fístula perianal|7; Doença pilonidal|5"),
            ]},
            {"code": "CIR-06", "name": "Cirurgia vascular e urologia", "weight": 10, "families": [
                M("CIR-VAS-01", "Doença arterial de membros", 80, "Isquemia aguda de membros|9; Doença arterial obstrutiva periférica|8; Pé diabético|8"),
                M("CIR-VAS-02", "Aorta", 75, "Aneurisma de aorta abdominal|9; Dissecção de aorta|8"),
                M("CIR-VAS-03", "Doença venosa", 65, "Trombose venosa profunda|8; Insuficiência venosa crônica e varizes|6; Úlceras vasculares|6"),
                M("CIR-URO-01", "Litíase urinária", 60, "Litíase urinária|9"),
                M("CIR-URO-02", "Escroto agudo", 60, "Escroto agudo e torção testicular|9"),
                M("CIR-URO-03", "Trato urinário baixo e próstata", 75, "Retenção urinária aguda|8; Hiperplasia prostática benigna|8; Câncer de próstata|8"),
                M("CIR-URO-04", "Trauma urológico", 55, "Trauma de uretra e bexiga|7"),
                M("CIR-URO-05", "Oncologia urinária", 55, "Câncer de rim|5; Câncer de bexiga|5"),
            ]},
            {"code": "CIR-07", "name": "Oncologia, tórax e cirurgia endócrina", "weight": 6, "families": [
                M("CIR-ONC-01", "Princípios oncológicos", 65, "Princípios da cirurgia oncológica|8; Estadiamento TNM|8; Linfonodo sentinela|7"),
                M("CIR-TOR-01", "Neoplasia pulmonar", 60, "Câncer de pulmão|7; Nódulo pulmonar|6"),
                M("CIR-TOR-02", "Doença pleural cirúrgica", 55, "Empiema|7; Derrame pleural cirúrgico|6"),
                M("CIR-END-01", "Cirurgia endócrina", 65, "Nódulo tireoidiano|7; Câncer de tireoide|7; Hiperparatireoidismo|5; Tumores adrenais|4"),
                M("CIR-ONC-02", "Melanoma e mama", 60, "Melanoma|7; Câncer de mama: princípios cirúrgicos|7"),
            ]},
            {"code": "CIR-08", "name": "Cirurgia pediátrica, plástica, transplantes e técnica", "weight": 4, "families": [
                M("CIR-PED-01", "Obstruções e malformações pediátricas", 65, "Estenose hipertrófica do piloro|7; Invaginação intestinal|7; Doença de Hirschsprung|6; Atresias intestinais|5"),
                M("CIR-PED-02", "Parede e urologia pediátrica", 55, "Gastrosquise e onfalocele|6; Criptorquidia|6; Hérnia inguinal pediátrica|6"),
                M("CIR-TRP-01", "Doação e transplantes", 50, "Doação de órgãos e transplantes|6"),
                M("CIR-TEC-01", "Técnica operatória", 60, "Hemostasia cirúrgica|6; Fios e suturas|5; Videolaparoscopia|5"),
                M("CIR-PLA-01", "Feridas e reconstrução", 50, "Úlceras por pressão|5; Enxertos e retalhos|4"),
                M("CIR-BAR-01", "Cirurgia bariátrica", 45, "Cirurgia bariátrica|5"),
            ]},
        ],
    },
    {
        "code": "PED", "name": "Pediatria", "color": "#0EA5E9",
        "blocks": [
            {"code": "PED-01", "name": "Neonatologia", "weight": 24, "families": [
                M("PED-NEO-01", "Sala de parto", 95, "Reanimação neonatal|10; Assistência imediata ao recém-nascido|10"),
                M("PED-NEO-02", "Prematuridade e classificação", 80, "Prematuridade|10; Classificação por idade gestacional e peso|9"),
                M("PED-NEO-03", "Icterícia e hemólise", 90, "Icterícia neonatal|10; Incompatibilidade ABO/Rh e doença hemolítica|9"),
                M("PED-NEO-04", "Infecção neonatal", 85, "Sepse neonatal|10; Infecções congênitas|8"),
                M("PED-NEO-05", "Aleitamento neonatal", 65, "Aleitamento materno|10"),
                M("PED-NEO-06", "Desconforto respiratório neonatal", 90, "Síndrome do desconforto respiratório|9; Taquipneia transitória|8; Aspiração meconial|8"),
                M("PED-NEO-07", "Metabolismo e filhos de mães de risco", 70, "Hipoglicemia neonatal|9; Recém-nascido de mãe diabética|8"),
                M("PED-NEO-08", "Triagens e alta", 70, "Triagens neonatais|9; Alta segura do recém-nascido|8"),
                M("PED-NEO-09", "Complicações do prematuro", 70, "Enterocolite necrosante|7; Persistência do canal arterial|6; Hemorragia peri-intraventricular|6; Displasia broncopulmonar|5"),
            ]},
            {"code": "PED-02", "name": "Puericultura, crescimento e nutrição", "weight": 16, "families": [
                M("PED-PUE-01", "Crescimento", 75, "Crescimento infantil|10; Baixa estatura|8; Falha de crescimento|8"),
                M("PED-PUE-02", "Desenvolvimento", 70, "Desenvolvimento neuropsicomotor|10"),
                M("PED-PUE-03", "Alimentação infantil", 90, "Aleitamento materno|10; Introdução alimentar|10; Alimentação do lactente e pré-escolar|9"),
                M("PED-PUE-04", "Puericultura e prevenção", 70, "Puericultura na atenção primária|9; Prevenção de acidentes|8"),
                M("PED-PUE-05", "Suplementações", 55, "Suplementação de ferro|9; Suplementação de vitamina D|8"),
                M("PED-PUE-06", "Distúrbios nutricionais", 70, "Desnutrição|9; Obesidade infantil|8"),
                M("PED-PUE-07", "Sono e saúde bucal", 50, "Sono seguro e morte súbita|8; Saúde bucal|5"),
            ]},
            {"code": "PED-03", "name": "Imunizações e infectologia", "weight": 16, "families": [
                M("PED-VAC-01", "Vacinação infantil I", 70, "Calendário vacinal da criança|10"),
                M("PED-VAC-02", "Vacinação infantil II", 70, "Calendário do adolescente|9; Atraso vacinal|9"),
                M("PED-VAC-03", "Vacinação especial III", 70, "Contraindicações e falsas contraindicações|9; Vacinas especiais e CRIE|8; Eventos adversos pós-vacinação|7"),
                M("PED-INF-01", "Doenças exantemáticas", 70, "Doenças exantemáticas|9; Escarlatina|8"),
                M("PED-INF-02", "Infecções invasivas", 75, "Meningite bacteriana|9; Sepse pediátrica|9"),
                M("PED-INF-03", "Infecção urinária pediátrica", 60, "Infecção urinária pediátrica|9"),
                M("PED-INF-04", "Infecções verticais", 65, "Sífilis congênita|9; HIV na infância e transmissão vertical|6"),
                M("PED-INF-05", "Infecções respiratórias específicas", 65, "Coqueluche|8; Tuberculose na infância|7"),
                M("PED-INF-06", "Infecções endêmicas e sistêmicas", 60, "Dengue na criança|7; Parasitoses intestinais|6; Mononucleose|6"),
            ]},
            {"code": "PED-04", "name": "Pneumologia", "weight": 13, "families": [
                M("PED-PNE-01", "Asma e sibilância", 85, "Asma pediátrica|10; Sibilância recorrente|8"),
                M("PED-PNE-02", "Bronquiolite", 65, "Bronquiolite viral aguda|10"),
                M("PED-PNE-03", "Infecções pulmonares", 75, "Pneumonia adquirida na comunidade|10; Tuberculose pulmonar pediátrica|7"),
                M("PED-PNE-04", "Obstrução de via aérea superior", 70, "Corpo estranho em via aérea|9; Laringite viral|8; Epiglotite|7"),
                M("PED-PNE-05", "Insuficiência respiratória e oxigênio", 70, "Insuficiência respiratória pediátrica|9; Oxigenoterapia|8"),
                M("PED-PNE-06", "Fibrose cística", 50, "Fibrose cística|6"),
            ]},
            {"code": "PED-05", "name": "Gastroenterologia e hidratação", "weight": 11, "families": [
                M("PED-GAS-01", "Diarreia e desidratação", 100, "Diarreia aguda|10; Desidratação|10; Planos A, B e C|10; Terapia de reidratação oral|9"),
                M("PED-GAS-02", "Constipação", 50, "Constipação funcional|8"),
                M("PED-GAS-03", "Emergências gastrointestinais", 65, "Invaginação intestinal|8; Estenose hipertrófica do piloro|7"),
                M("PED-GAS-04", "Diarreia crônica e má absorção", 65, "Diarreia persistente e crônica|7; Doença celíaca|6; Intolerância à lactose|5"),
                M("PED-GAS-05", "Refluxo e alergia alimentar", 65, "Refluxo gastroesofágico|7; Alergia à proteína do leite de vaca|7; Dor abdominal recorrente|6"),
                M("PED-GAS-06", "Hepatologia pediátrica", 50, "Hepatites e colestase|5"),
            ]},
            {"code": "PED-06", "name": "Emergências e neurologia", "weight": 10, "families": [
                M("PED-EME-01", "Ressuscitação pediátrica", 75, "Parada cardiorrespiratória pediátrica|10"),
                M("PED-EME-02", "Choque pediátrico", 80, "Choque pediátrico|10; Choque séptico|9"),
                M("PED-EME-03", "Anafilaxia", 55, "Anafilaxia|10"),
                M("PED-EME-04", "Convulsões e epilepsia", 75, "Convulsão febril|9; Estado de mal epiléptico|9; Epilepsia na infância|7"),
                M("PED-EME-05", "Neuroinfecção", 60, "Meningite e encefalite|9"),
                M("PED-EME-06", "Violência infantil", 60, "Maus-tratos e violência infantil|9"),
                M("PED-EME-07", "Emergências externas", 70, "Trauma cranioencefálico pediátrico|7; Intoxicações pediátricas|7; Afogamento|6; Queimaduras na criança|6"),
            ]},
            {"code": "PED-07", "name": "Nefrologia, cardiologia, endocrinologia e hematologia", "weight": 7, "families": [
                M("PED-ESP-01", "Diabetes tipo 1", 70, "Diabetes mellitus tipo 1|8; Cetoacidose diabética pediátrica|9"),
                M("PED-ESP-02", "Hematologia pediátrica", 70, "Anemia ferropriva|9; Doença falciforme|7; Púrpura trombocitopênica imune|6"),
                M("PED-ESP-03", "Nefrologia pediátrica", 75, "Síndrome nefrótica|8; Síndrome nefrítica|8; Lesão renal aguda|7; Refluxo vesicoureteral|6"),
                M("PED-ESP-04", "Cardiologia pediátrica", 80, "Sopros cardíacos|8; Cardiopatias congênitas acianóticas|8; Cardiopatias congênitas cianóticas|8; Insuficiência cardíaca na criança|7"),
                M("PED-ESP-05", "Puberdade", 50, "Puberdade precoce e tardia|6"),
            ]},
            {"code": "PED-08", "name": "Adolescência e complementares", "weight": 3, "families": [
                M("PED-ADO-01", "Saúde do adolescente", 75, "Consulta do adolescente e confidencialidade|8; Saúde sexual e contracepção|8; Saúde mental e risco de suicídio|8; Infecções sexualmente transmissíveis|7"),
                M("PED-DER-01", "Dermatologia pediátrica", 60, "Dermatite atópica|7; Impetigo e infecções cutâneas|7; Escabiose e pediculose|6"),
                M("PED-MUS-01", "Reumatologia e infecção osteoarticular", 65, "Febre reumática|7; Artrite séptica e osteomielite|7; Artrite idiopática juvenil|5"),
                M("PED-GEN-01", "Condições do desenvolvimento", 55, "Síndrome de Down|6; Displasia do desenvolvimento do quadril|6"),
                M("PED-ONC-01", "Oncologia pediátrica", 50, "Leucemias e linfomas pediátricos|5; Tumor de Wilms e neuroblastoma|4"),
            ]},
        ],
    },
    {
        "code": "PRE", "name": "Medicina Preventiva", "color": "#10B981",
        "blocks": [
            {"code": "PRE-01", "name": "SUS e Atenção Primária", "weight": 30, "families": [
                M("PRE-SUS-01", "Fundamentos legais do SUS", 90, "Princípios doutrinários do SUS|10; Princípios organizativos do SUS|10; Lei 8.080/1990|10; Lei 8.142/1990|9"),
                M("PRE-SUS-02", "Atenção Básica e ESF", 75, "Política Nacional de Atenção Básica|10; Estratégia Saúde da Família|10"),
                M("PRE-SUS-03", "Atributos da APS", 75, "Atributos essenciais da APS|10; Atributos derivados da APS|8; Coordenação do cuidado|9"),
                M("PRE-SUS-04", "Redes e regionalização", 75, "Regionalização e hierarquização|9; Redes de Atenção à Saúde|9; Linhas de cuidado|7; Redes temáticas|7"),
                M("PRE-SUS-05", "Território, família e domicílio", 70, "Territorialização e adscrição|9; Visita domiciliar|8; Genograma e ecomapa|7"),
                M("PRE-SUS-06", "Financiamento do SUS", 55, "Financiamento do SUS|8"),
                M("PRE-SUS-07", "Cuidado compartilhado e prevenção", 65, "Apoio matricial|8; Projeto terapêutico singular|8; Prevenção quaternária|8"),
            ]},
            {"code": "PRE-02", "name": "Epidemiologia e bioestatística", "weight": 25, "families": [
                M("PRE-EPI-01", "Medidas de frequência e ocorrência", 80, "Incidência|10; Prevalência|10; Mortalidade|9; Letalidade|9"),
                M("PRE-EPI-02", "Testes diagnósticos I", 90, "Sensibilidade|10; Especificidade|10; Valor preditivo positivo|10; Valor preditivo negativo|10"),
                M("PRE-EPI-03", "Testes diagnósticos II", 75, "Razões de verossimilhança|9; Curva ROC|8; Testes diagnósticos em série e paralelo|8"),
                M("PRE-EPI-04", "Medidas de associação e impacto", 100, "Risco relativo|10; Odds ratio|10; Hazard ratio|7; Número necessário para tratar|10; Número necessário para causar dano|9; Redução absoluta do risco|9; Redução relativa do risco|9"),
                M("PRE-EPI-05", "Erros causais", 80, "Viés|10; Confundimento|10; Modificação de efeito e interação|7"),
                M("PRE-EPI-06", "Inferência estatística", 85, "Intervalo de confiança|9; Valor de p|9; Poder estatístico e erros tipo I e II|8"),
                M("PRE-EPI-07", "Demografia e carga de doença", 60, "Transição demográfica e epidemiológica|8; Indicadores demográficos|7; Morbidade e carga de doença|7"),
            ]},
            {"code": "PRE-03", "name": "Medicina Baseada em Evidências", "weight": 12, "families": [
                M("PRE-MBE-01", "Estudos observacionais", 80, "Estudo de coorte|10; Estudo caso-controle|10; Estudo transversal|9; Estudo ecológico|7"),
                M("PRE-MBE-02", "Ensaios clínicos", 90, "Ensaio clínico randomizado|10; Randomização e ocultação de alocação|9; Intenção de tratar|9; Cegamento|8; Perdas de seguimento|8"),
                M("PRE-MBE-03", "Síntese de evidências", 80, "Revisão sistemática|9; Metanálise|9; Heterogeneidade|8"),
                M("PRE-MBE-04", "Estudos diagnósticos", 60, "Estudos de acurácia diagnóstica|8"),
                M("PRE-MBE-05", "Validade e graduação", 75, "Validade interna|9; Aplicabilidade e validade externa|8; Níveis de evidência|8; Graus de recomendação|7; GRADE|6"),
            ]},
            {"code": "PRE-04", "name": "Rastreamento e imunizações", "weight": 15, "families": [
                M("PRE-RAS-01", "Fundamentos do rastreamento", 60, "Princípios do rastreamento|10"),
                M("PRE-RAS-02", "Rastreamento feminino", 75, "Rastreamento do câncer do colo do útero|10; Rastreamento do câncer de mama|10"),
                M("PRE-RAS-03", "Rastreamento gastrointestinal e urológico", 70, "Rastreamento do câncer colorretal|9; Rastreamento do câncer de próstata|8"),
                M("PRE-RAS-04", "Rastreamento cardiometabólico e ósseo", 75, "Rastreamento de hipertensão|9; Rastreamento de diabetes|9; Rastreamento de dislipidemia|8; Rastreamento de osteoporose|8"),
                M("PRE-RAS-05", "Rastreamentos seletivos", 55, "Rastreamento do câncer de pulmão|7; Rastreamento de aneurisma de aorta abdominal|7"),
                M("PRE-VAC-01", "Vacinação por ciclo de vida I", 80, "Calendário vacinal da criança|10; Calendário do adolescente|9"),
                M("PRE-VAC-02", "Vacinação por ciclo de vida II", 80, "Calendário do adulto|9; Calendário do idoso|9; Vacinação da gestante|10"),
                M("PRE-VAC-03", "Vacinação especial III", 75, "Contraindicações e falsas contraindicações vacinais|9; Vacinas em imunossuprimidos|8; CRIE|8; Eventos adversos pós-vacinação|7"),
            ]},
            {"code": "PRE-05", "name": "Ética médica e bioética", "weight": 8, "families": [
                M("PRE-ETI-01", "Autonomia e confidencialidade", 75, "Sigilo profissional|10; Consentimento livre e esclarecido|10; Autonomia e capacidade decisória|9"),
                M("PRE-ETI-02", "Documentos médicos", 70, "Prontuário médico|9; Declaração de óbito|9; Atestado médico|8"),
                M("PRE-ETI-03", "Responsabilidade e comunicação", 65, "Responsabilidade ética, civil e penal|8; Relação médico-paciente|8; Publicidade médica|7; Telemedicina|6"),
                M("PRE-ETI-04", "Bioética e fim de vida", 75, "Princípios da bioética|9; Diretivas antecipadas de vontade|8; Ortotanásia, distanásia e eutanásia|8; Cuidados paliativos|8"),
                M("PRE-ETI-05", "Ética em pesquisa", 50, "Ética em pesquisa|7"),
            ]},
            {"code": "PRE-06", "name": "Vigilância, saúde coletiva e gestão", "weight": 10, "families": [
                M("PRE-VIG-01", "Vigilância epidemiológica", 80, "Notificação compulsória|10; Vigilância epidemiológica|9; Investigação de surtos|9"),
                M("PRE-VIG-02", "Saúde ocupacional", 70, "Exposição ocupacional a material biológico|9; Acidente de trabalho e CAT|8"),
                M("PRE-VIG-03", "Promoção e determinantes", 70, "Níveis de prevenção|9; Promoção da saúde|8; Determinantes sociais da saúde|8; Educação em saúde|7; Saúde de populações vulnerabilizadas|7"),
                M("PRE-VIG-04", "Campos da vigilância", 60, "Vigilância sanitária|8; Vigilância ambiental|7; Vigilância em saúde do trabalhador|8"),
                M("PRE-GES-01", "Segurança e qualidade", 60, "Segurança do paciente|8; Qualidade assistencial|6"),
                M("PRE-GES-02", "Planejamento e gestão", 65, "Planejamento em saúde|7; Avaliação de serviços e indicadores|7; Regulação assistencial|7; Economia da saúde|5; LGPD em saúde|5"),
            ]},
        ],
    },
    {
        "code": "GO", "name": "Ginecologia e Obstetrícia", "color": "#F59E0B",
        "blocks": [
            {"code": "GO-01", "name": "Pré-natal e medicina fetal", "weight": 19, "families": [
                M("GO-PRE-01", "Pré-natal e risco", 90, "Assistência pré-natal de risco habitual|10; Estratificação de risco gestacional|10"),
                M("GO-PRE-02", "Datação e ultrassonografia", 75, "Diagnóstico e datação da gestação|9; Ultrassonografia obstétrica|8"),
                M("GO-PRE-03", "Exames e infecções", 80, "Exames laboratoriais do pré-natal|10; Rastreamento de infecções na gestação|9"),
                M("GO-PRE-04", "Vacinas e suplementação", 75, "Vacinação na gestação|10; Suplementação na gestação|9"),
                M("GO-PRE-05", "Crescimento e vitalidade fetal", 80, "Vitalidade fetal|9; Restrição de crescimento fetal|9; Macrossomia fetal|8"),
                M("GO-PRE-06", "Isoimunização Rh", 60, "Isoimunização Rh|9"),
                M("GO-PRE-07", "Gestações e infecções especiais", 65, "Gestação gemelar|8; Infecções congênitas|8"),
                M("GO-PRE-08", "Planejamento e segurança medicamentosa", 55, "Uso de medicamentos na gestação|7; Aconselhamento pré-concepcional|7"),
            ]},
            {"code": "GO-02", "name": "Síndromes hipertensivas e distúrbios metabólicos", "weight": 16, "families": [
                M("GO-HIP-01", "Hipertensão na gestação", 110, "Pré-eclâmpsia|10; Pré-eclâmpsia com sinais de gravidade|10; Eclâmpsia|10; Síndrome HELLP|10; Hipertensão gestacional|9; Hipertensão crônica na gestação|8"),
                M("GO-MET-01", "Diabetes na gestação", 80, "Diabetes gestacional|10; Diabetes pré-gestacional|8"),
                M("GO-MET-02", "Tromboembolismo na gestação", 55, "Tromboembolismo na gestação|8"),
                M("GO-MET-03", "Outras doenças clínicas da gestação", 65, "Doenças tireoidianas na gestação|7; Hiperêmese gravídica|7; Colestase intra-hepática da gestação|6"),
            ]},
            {"code": "GO-03", "name": "Gestação inicial, abortamento e hemorragias", "weight": 12, "families": [
                M("GO-INI-01", "Abortamento", 90, "Abortamento|10; Abortamento retido, incompleto e infectado|9; Ameaça de abortamento|8"),
                M("GO-INI-02", "Ectópica e doença trofoblástica", 80, "Gravidez ectópica|10; Doença trofoblástica gestacional|9"),
                M("GO-HEM-01", "Hemorragia da segunda metade", 90, "Placenta prévia|10; Descolamento prematuro de placenta|10; Vasa prévia|7"),
                M("GO-MEM-01", "Membranas e infecção", 75, "Rotura prematura de membranas|9; Corioamnionite|9"),
                M("GO-PRE-09", "Prematuridade", 70, "Trabalho de parto prematuro|9; Insuficiência istmocervical|6"),
            ]},
            {"code": "GO-04", "name": "Trabalho de parto, puerpério e emergências", "weight": 18, "families": [
                M("GO-PAR-01", "Trabalho de parto", 85, "Fisiologia e diagnóstico do trabalho de parto|10; Partograma|10"),
                M("GO-PAR-02", "Condução e via de parto", 90, "Indução do parto|9; Assistência ao parto vaginal|9; Indicações de cesariana|9"),
                M("GO-DIS-01", "Distócias", 75, "Distócia de ombros|10; Distócia de progressão|9"),
                M("GO-HPP-01", "Hemorragia pós-parto", 105, "Hemorragia pós-parto|10; Atonia uterina|10; Trauma do canal de parto|9; Retenção placentária e acretismo|9; Coagulopatia obstétrica|8"),
                M("GO-EME-01", "Emergências mecânicas", 70, "Prolapso de cordão|9; Rotura uterina|9"),
                M("GO-PUE-01", "Puerpério", 75, "Puerpério fisiológico|8; Infecção puerperal|9; Mastite puerperal|8"),
                M("GO-EME-02", "Emergências maternas críticas", 65, "Parada cardiorrespiratória materna|8; Embolia por líquido amniótico|6"),
                M("GO-PAR-03", "Situações especiais do parto", 65, "Parto pélvico|7; Parto instrumental|7; Analgesia de parto|6"),
            ]},
            {"code": "GO-05", "name": "Contracepção e endocrinologia reprodutiva", "weight": 11, "families": [
                M("GO-CON-01", "Métodos e planejamento", 65, "Métodos contraceptivos|9; Planejamento reprodutivo|8"),
                M("GO-CON-02", "Dispositivo intrauterino", 60, "Dispositivo intrauterino|9"),
                M("GO-CON-03", "Contracepção hormonal e emergência", 75, "Contraceptivos combinados|9; Contraceptivos apenas com progestagênio|8; Contracepção de emergência|9"),
                M("GO-END-01", "Amenorreia e prolactina", 70, "Amenorreia primária|8; Amenorreia secundária|8; Hiperprolactinemia|7"),
                M("GO-END-02", "Síndrome dos ovários policísticos", 60, "Síndrome dos ovários policísticos|9"),
                M("GO-END-03", "Climatério", 65, "Climatério e menopausa|8; Terapia hormonal|7"),
                M("GO-REP-01", "Reprodução e função ovariana", 65, "Infertilidade|7; Insuficiência ovariana prematura|6; Puberdade precoce e tardia|6"),
            ]},
            {"code": "GO-06", "name": "Ginecologia benigna, urogin e infecções", "weight": 10, "families": [
                M("GO-BEN-01", "Sangramento e doenças uterinas", 85, "Sangramento uterino anormal|9; Miomatose|8; Adenomiose|7; Dismenorreia|7"),
                M("GO-INF-01", "Infecção genital", 80, "Doença inflamatória pélvica|9; Infecções sexualmente transmissíveis|8; Cervicites|8; Vulvovaginites|8"),
                M("GO-END-04", "Endometriose e dor", 70, "Endometriose|9; Dor pélvica crônica|7"),
                M("GO-ANE-01", "Massas e emergência anexial", 65, "Torção anexial|8; Cistos e massas anexiais benignas|7"),
                M("GO-URO-01", "Uroginecologia", 70, "Incontinência urinária|8; Prolapso genital|8; Fístulas geniturinárias|6"),
            ]},
            {"code": "GO-07", "name": "Prevenção, mastologia e oncologia", "weight": 14, "families": [
                M("GO-CER-01", "Rastreamento cervical", 85, "Rastreamento do câncer do colo do útero|10; Citologia cervical alterada|9; HPV|8"),
                M("GO-CER-02", "Lesões e câncer cervical", 80, "Lesões intraepiteliais|9; Colposcopia|8; Câncer do colo do útero|9"),
                M("GO-MAS-01", "Avaliação mamária", 80, "Rastreamento do câncer de mama|10; Nódulo mamário|9; Alterações benignas da mama|7; Descarga papilar|7; Mastite não puerperal|6"),
                M("GO-MAS-02", "Câncer de mama", 70, "Câncer de mama|9"),
                M("GO-ONC-01", "Oncologia ginecológica", 80, "Câncer de endométrio|8; Câncer de ovário|8; Doença trofoblástica neoplásica|7; Neoplasias vulvares e vaginais|6"),
            ]},
        ],
    },
]


def seed_catalog(db: Database) -> None:
    if db.scalar("SELECT COUNT(*) FROM areas", default=0):
        return
    with db.transaction() as con:
        for area_order, area in enumerate(CATALOG, 1):
            cur = con.execute(
                "INSERT INTO areas(code, name, color, sort_order) VALUES(?,?,?,?)",
                (area["code"], area["name"], area["color"], area_order),
            )
            area_id = cur.lastrowid
            for block_order, block in enumerate(area["blocks"], 1):
                cur = con.execute(
                    "INSERT INTO blocks(area_id, code, name, weight, sort_order) VALUES(?,?,?,?,?)",
                    (area_id, block["code"], block["name"], block["weight"], block_order),
                )
                block_id = cur.lastrowid
                for family_order, family in enumerate(block["families"], 1):
                    cur = con.execute(
                        "INSERT INTO macro_families(block_id, code, name, base_priority, estimated_minutes, sort_order) "
                        "VALUES(?,?,?,?,?,?)",
                        (block_id, family["code"], family["name"], family["priority"], family["minutes"], family_order),
                    )
                    macro_id = cur.lastrowid
                    for item_order, (title, priority) in enumerate(family["items"], 1):
                        source_code = f"{family['code']}-{item_order:02d}"
                        con.execute(
                            "INSERT INTO content_items(macro_family_id, source_code, title, original_priority, sort_order) "
                            "VALUES(?,?,?,?,?)",
                            (macro_id, source_code, title, priority, item_order),
                        )
