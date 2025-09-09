import csv
import os
import shutil
import re
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional

# Configurações
CSV_PATH = os.path.join("data", "corridas.csv")
BACKUP_DIR = os.path.join("data", "backups")
HEADERS = ["Título", "Data", "Local", "Link", "Fonte", "Hash"]

def garantir_diretorio():
    """Garante que os diretórios necessários existam"""
    os.makedirs("data", exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

def criar_backup() -> Optional[str]:
    """Cria backup do CSV atual com timestamp"""
    if not os.path.exists(CSV_PATH):
        print("📄 Nenhum CSV para fazer backup")
        return None
    
    garantir_diretorio()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"corridas_backup_{timestamp}.csv"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    try:
        shutil.copy2(CSV_PATH, backup_path)
        print(f"💾 Backup criado: {backup_filename}")
        return backup_path
    except Exception as e:
        print(f"❌ Erro ao criar backup: {e}")
        return None

def limpar_csv():
    """Inicializa o CSV com headers corretos"""
    garantir_diretorio()
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)

def carregar_eventos_existentes() -> Set[str]:
    """Carrega hashes dos eventos já existentes no CSV"""
    if not os.path.exists(CSV_PATH):
        return set()
    
    hashes_existentes = set()
    try:
        with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'Hash' in row and row['Hash']:
                    hashes_existentes.add(row['Hash'])
                else:
                    # Fallback: gera hash baseado nos dados
                    titulo = row.get('Título', '').strip()
                    data = row.get('Data', '').strip()
                    local = row.get('Local', '').strip()
                    if titulo and data:
                        hash_fallback = gerar_hash_evento(titulo, data, local)
                        hashes_existentes.add(hash_fallback)
    except Exception as e:
        print(f"⚠️ Erro ao carregar eventos existentes: {e}")
    
    return hashes_existentes

def gerar_hash_evento(titulo: str, data: str, local: str) -> str:
    """Gera hash único e consistente para um evento"""
    import hashlib
    conteudo = f"{titulo.lower().strip()}{data.strip()}{local.lower().strip()}"
    return hashlib.md5(conteudo.encode()).hexdigest()[:8]

def salvar_eventos(eventos: List[Dict]) -> int:
    """
    Salva eventos no CSV, evitando duplicatas
    Retorna o número de eventos realmente salvos
    """
    if not eventos:
        print("⚠️ Nenhum evento para salvar")
        return 0
    
    garantir_diretorio()
    
    # Carrega hashes existentes
    hashes_existentes = carregar_eventos_existentes()
    
    # Se CSV não existe, cria com headers
    csv_existe = os.path.exists(CSV_PATH)
    if not csv_existe:
        limpar_csv()
    
    eventos_salvos = 0
    eventos_duplicados = 0
    
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            for evento in eventos:
                hash_evento = evento.get('hash', '')
                
                # Pula duplicatas
                if hash_evento in hashes_existentes:
                    eventos_duplicados += 1
                    continue
                
                # Prepara dados para CSV
                row = [
                    evento.get('titulo', 'Sem título'),
                    evento.get('data', 'Data não informada'),
                    evento.get('local', 'Local não informado'),
                    evento.get('link', ''),
                    evento.get('fonte', 'Fonte desconhecida'),
                    hash_evento
                ]
                
                writer.writerow(row)
                hashes_existentes.add(hash_evento)
                eventos_salvos += 1
        
        print(f"💾 {eventos_salvos} novos eventos salvos no CSV")
        if eventos_duplicados > 0:
            print(f"🔄 {eventos_duplicados} duplicatas ignoradas")
            
    except Exception as e:
        print(f"❌ Erro ao salvar eventos: {e}")
        return 0
    
    return eventos_salvos

def formatar_data(data_str: str) -> str:
    """
    Formata datas de diferentes padrões para DD/MM/YYYY
    Mais robusto que a versão anterior
    """
    if not data_str or not isinstance(data_str, str):
        return "Data não informada"
    
    # Remove espaços extras e caracteres estranhos
    data_limpa = re.sub(r'\s+', ' ', data_str.strip())
    
    # Padrões de data mais comuns
    padroes = [
        # "Dom 17/08/2025" -> "17/08/2025"
        r'^(?:Dom|Seg|Ter|Qua|Qui|Sex|S[áa]b)\s+(\d{1,2}/\d{1,2}/\d{4})$',
        # "17/08/2025"
        r'^(\d{1,2}/\d{1,2}/\d{4})$',
        # "17-08-2025"
        r'^(\d{1,2})-(\d{1,2})-(\d{4})$',
        # "2025-08-17"
        r'^(\d{4})-(\d{1,2})-(\d{1,2})$',
    ]
    
    for padrao in padroes:
        match = re.match(padrao, data_limpa)
        if match:
            if len(match.groups()) == 1:
                # Padrão já está correto (DD/MM/YYYY)
                return match.group(1)
            elif len(match.groups()) == 3:
                if padrao.endswith(r'(\d{4})$'):  # DD-MM-YYYY
                    dia, mes, ano = match.groups()
                    return f"{dia.zfill(2)}/{mes.zfill(2)}/{ano}"
                else:  # YYYY-MM-DD
                    ano, mes, dia = match.groups()
                    return f"{dia.zfill(2)}/{mes.zfill(2)}/{ano}"
    
    # Tentativa de parsing mais agressiva
    try:
        # Remove palavras comuns
        data_numerica = re.sub(r'[^\d\-/]', '', data_limpa)
        if '/' in data_numerica:
            partes = data_numerica.split('/')
            if len(partes) == 3:
                dia, mes, ano = partes
                return f"{dia.zfill(2)}/{mes.zfill(2)}/{ano}"
    except:
        pass
    
    # Se nada funcionou, retorna original ou placeholder
    return data_limpa if data_limpa else "Data não informada"

def validar_evento(evento: Dict) -> Tuple[bool, str]:
    """
    Valida se um evento tem dados mínimos necessários
    Retorna (é_válido, motivo_se_inválido)
    """
    titulo = evento.get('titulo', '').strip()
    data = evento.get('data', '').strip()
    
    if not titulo or len(titulo) < 3:
        return False, "Título muito curto ou vazio"
    
    if not data or data == "Data não informada":
        return False, "Data inválida ou não informada"
    
    # Verifica se a data está num formato minimamente válido
    if not re.match(r'\d{1,2}/\d{1,2}/\d{4}', data):
        return False, f"Formato de data inválido: {data}"
    
    return True, ""

def estatisticas_csv() -> Dict:
    """Retorna estatísticas do CSV atual"""
    if not os.path.exists(CSV_PATH):
        return {"total": 0, "por_fonte": {}, "arquivo_existe": False}
    
    estatisticas = {
        "total": 0,
        "por_fonte": {},
        "arquivo_existe": True,
        "eventos_futuros": 0,
        "eventos_passados": 0
    }
    
    try:
        with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            hoje = datetime.now().date()
            
            for row in reader:
                estatisticas["total"] += 1
                
                # Por fonte
                fonte = row.get('Fonte', 'Desconhecida')
                estatisticas["por_fonte"][fonte] = estatisticas["por_fonte"].get(fonte, 0) + 1
                
                # Eventos futuros vs passados
                try:
                    data_evento = datetime.strptime(row.get('Data', ''), '%d/%m/%Y').date()
                    if data_evento >= hoje:
                        estatisticas["eventos_futuros"] += 1
                    else:
                        estatisticas["eventos_passados"] += 1
                except:
                    pass
                    
    except Exception as e:
        print(f"⚠️ Erro ao calcular estatísticas: {e}")
    
    return estatisticas

def limpar_backups_antigos(manter_dias: int = 30):
    """Remove backups mais antigos que X dias"""
    if not os.path.exists(BACKUP_DIR):
        return
    
    limite = datetime.now().timestamp() - (manter_dias * 24 * 3600)
    removidos = 0
    
    try:
        for arquivo in os.listdir(BACKUP_DIR):
            if arquivo.startswith("corridas_backup_") and arquivo.endswith(".csv"):
                caminho = os.path.join(BACKUP_DIR, arquivo)
                if os.path.getmtime(caminho) < limite:
                    os.remove(caminho)
                    removidos += 1
        
        if removidos > 0:
            print(f"🧹 {removidos} backups antigos removidos")
            
    except Exception as e:
        print(f"⚠️ Erro ao limpar backups: {e}")

# Função de conveniência para debug
def debug_evento(evento: Dict):
    """Imprime evento formatado para debug"""
    print("🐛 DEBUG EVENTO:")
    for key, value in evento.items():
        if key != 'data_obj':  # Pula objetos datetime
            print(f"   {key}: {value}")
    print("   " + "-"*40)