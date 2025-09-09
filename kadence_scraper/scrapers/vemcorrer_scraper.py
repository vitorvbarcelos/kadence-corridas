import time
import hashlib
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

def gerar_hash_evento(titulo, data, local):
    """Gera hash único para evitar duplicatas"""
    conteudo = f"{titulo.lower().strip()}{data}{local.lower().strip()}"
    return hashlib.md5(conteudo.encode()).hexdigest()[:8]

def limpar_texto(texto):
    """Remove caracteres especiais e normaliza texto"""
    if not texto:
        return ""
    texto = re.sub(r'\s+', ' ', texto.strip())
    texto = texto.replace(',', ' ')  # Remove vírgulas para não quebrar CSV
    return texto

def processar_data_vemcorrer(dia_str, mes_str, ano_atual=None):
    """Processa data do formato VemCorrer: dia='16', mês='Ago' -> '16/08/2025'"""
    if not dia_str or not mes_str:
        return None, None
    
    # Mapeia meses em português (abreviado)
    meses = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
        'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
    }
    
    try:
        dia = dia_str.strip().zfill(2)
        mes_texto = mes_str.strip().lower()
        mes_num = meses.get(mes_texto, '01')
        
        # Se não foi passado ano, assume ano atual ou próximo
        if not ano_atual:
            ano_atual = datetime.now().year
        
        data_str_formatada = f"{dia}/{mes_num}/{ano_atual}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            # Se a data já passou, assume ano seguinte
            if data_obj < datetime.now():
                data_obj = datetime.strptime(f"{dia}/{mes_num}/{ano_atual + 1}", '%d/%m/%Y')
                data_str_formatada = f"{dia}/{mes_num}/{ano_atual + 1}"
            
            return data_obj, data_str_formatada
        except ValueError:
            pass
    except:
        pass
    
    return None, f"{dia_str}/{mes_str}"

def extrair_data_do_datetime(datetime_str):
    """Extrai ano do atributo datetime se disponível"""
    if not datetime_str:
        return None
    
    # Formato: "2025-08-16" ou "2025-08-16/2025-08-17"
    try:
        # Pega a primeira data se for um range
        primeira_data = datetime_str.split('/')[0] if '/' in datetime_str else datetime_str
        return datetime.strptime(primeira_data, '%Y-%m-%d').year
    except:
        return None

def coletar_eventos_vemcorrer(page):
    """Coleta eventos de corrida do VemCorrer"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".evento")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector(".evento__nome")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                if not titulo:
                    continue
                
                # Data - pode ser simples ou dupla
                # Primeiro tenta data dupla (evento de múltiplos dias)
                data_dupla = card.query_selector(".evento__data--dupla")
                if data_dupla:
                    # Data de início
                    dia_inicio = card.query_selector(".evento__comeco .evento__dia")
                    mes_inicio = card.query_selector(".evento__comeco .evento__mes")
                    
                    if dia_inicio and mes_inicio:
                        # Tenta extrair ano do datetime se disponível
                        datetime_attr = card.query_selector(".evento__comeco")
                        ano = None
                        if datetime_attr:
                            datetime_value = datetime_attr.get_attribute("datetime")
                            ano = extrair_data_do_datetime(datetime_value)
                        
                        data_obj, data_formatada = processar_data_vemcorrer(
                            dia_inicio.inner_text(), 
                            mes_inicio.inner_text(),
                            ano
                        )
                    else:
                        continue
                else:
                    # Data simples
                    dia_el = card.query_selector(".evento__data .evento__dia")
                    mes_el = card.query_selector(".evento__data .evento__mes")
                    
                    if dia_el and mes_el:
                        # Tenta extrair ano do datetime se disponível
                        datetime_attr = card.query_selector(".evento__data time")
                        ano = None
                        if datetime_attr:
                            datetime_value = datetime_attr.get_attribute("datetime")
                            ano = extrair_data_do_datetime(datetime_value)
                        
                        data_obj, data_formatada = processar_data_vemcorrer(
                            dia_el.inner_text(), 
                            mes_el.inner_text(),
                            ano
                        )
                    else:
                        continue
                
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local - remove o ícone e pega só o texto
                local_el = card.query_selector(".evento__local")
                local = "Local não informado"
                if local_el:
                    local_text = limpar_texto(local_el.inner_text())
                    # Remove ícone (primeiro caractere geralmente)
                    local = re.sub(r'^[^\w\s]*\s*', '', local_text).strip()
                    local = limpar_texto(local)
                
                # Link - extrai do href do botão "Saiba Mais"
                link_el = card.query_selector("a[href*='evento/']")
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        # Converte para URL completa se necessário
                        if href.startswith("evento/"):
                            link = f"https://vemcorrer.com/{href}"
                        elif href.startswith("/evento/"):
                            link = f"https://vemcorrer.com{href}"
                        else:
                            link = href
                
                # Validações básicas
                if len(titulo.strip()) < 3:
                    continue
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                
                eventos.append({
                    "titulo": titulo,
                    "data": data_formatada,
                    "local": local,
                    "link": link,
                    "hash": evento_hash,
                    "fonte": "VemCorrer",
                    "data_obj": data_obj
                })
                
                # Mostra detalhes dos primeiros 3 eventos
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo[:35]}... | {data_formatada} | {local[:25]}...")
                
            except Exception as e:
                continue
        
        print(f"   🎯 Total de eventos válidos coletados: {len(eventos)}")
                
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_vemcorrer(max_tentativas=3):
    """Extrai eventos de corrida do VemCorrer"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 VemCorrer - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL dos eventos do VemCorrer
                url = "https://vemcorrer.com/evento/"
                
                try:
                    print("📄 Carregando VemCorrer...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(3)
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector(".evento", timeout=15000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Faz scroll para garantir que todos os eventos carregaram
                    print("🔄 Fazendo scroll para carregar todos os eventos...")
                    for i in range(3):  # Scroll algumas vezes para garantir
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1)
                    
                    # Coleta todos os eventos
                    total_cards = len(page.query_selector_all(".evento"))
                    print(f"🔄 Processando {total_cards} eventos...")
                    eventos = coletar_eventos_vemcorrer(page)
                    
                    browser.close()
                    
                    if eventos:
                        # Remove duplicatas internas
                        eventos_unicos = {}
                        for evento in eventos:
                            hash_evento = evento['hash']
                            if hash_evento not in eventos_unicos:
                                eventos_unicos[hash_evento] = evento
                        
                        eventos_finais = list(eventos_unicos.values())
                        eventos_finais.sort(key=lambda x: x['data_obj'])
                        
                        duplicatas = len(eventos) - len(eventos_finais)
                        
                        print(f"✅ VemCorrer: {len(eventos_finais)} eventos únicos coletados")
                        if duplicatas > 0:
                            print(f"🔄 {duplicatas} duplicatas internas removidas")
                        
                        return eventos_finais
                    else:
                        print("⚠️ Nenhum evento encontrado")
                        
                except TimeoutError:
                    print(f"❌ Timeout na tentativa {tentativa + 1}")
                    browser.close()
                    continue
                    
        except Exception as e:
            print(f"❌ Erro geral na tentativa {tentativa + 1}: {str(e)[:80]}...")
            if tentativa == max_tentativas - 1:
                print("💀 VemCorrer falhou após todas as tentativas")
            continue
    
    return eventos