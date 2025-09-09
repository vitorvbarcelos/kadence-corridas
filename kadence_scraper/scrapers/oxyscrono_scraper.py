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
    texto = texto.replace(',', ' ')  # Remove vírgulas para CSV
    return texto

def processar_data_oxyscrono(data_str):
    """Processa data do OxyScrono: '10/08/2025' -> data_obj + data_formatada"""
    if not data_str:
        return None, None
    
    try:
        data_obj = datetime.strptime(data_str, '%d/%m/%Y')
        return data_obj, data_str
    except ValueError:
        return None, None

def coletar_eventos_oxyscrono(page):
    """Coleta eventos do OxyScrono.com.br"""
    eventos = []
    
    try:
        # Aguarda os cards aparecerem
        page.wait_for_selector(".elemnt.celement", timeout=20000)
        
        # Scroll para carregar todos os eventos
        print("   🔄 Fazendo scroll para carregar todos os eventos...")
        for i in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
        
        # Seleciona todos os cards
        cards = page.query_selector_all(".elemnt.celement")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Data do evento
                data_el = card.query_selector(".blckbox .number")
                if not data_el:
                    continue
                    
                data_str = limpar_texto(data_el.inner_text())
                data_obj, data_formatada = processar_data_oxyscrono(data_str)
                
                if not data_obj or data_obj < datetime.now():
                    continue
                
                # Título do evento
                titulo_el = card.query_selector(".name.title-event")
                if not titulo_el:
                    continue
                    
                titulo = limpar_texto(titulo_el.inner_text())
                if len(titulo) < 5:
                    continue
                
                # Local - CORREÇÃO: pega especificamente o parágrafo com ícone fa-map-marker
                local = "Local não informado"
                local_el = card.query_selector("p:has(i.fa-map-marker)")
                if local_el:
                    local_text = local_el.inner_text()
                    # Remove o ícone e limpa o texto: "Abadia Dos Dourados - MG"
                    local_clean = re.sub(r'^\s*.*?fa-map-marker.*?\s*', '', local_text).strip()
                    if not local_clean:
                        # Fallback: remove qualquer coisa antes do primeiro texto válido
                        local_clean = re.sub(r'^\s*[^\w]*\s*', '', local_text).strip()
                    
                    if local_clean and len(local_clean) > 3:
                        local = limpar_texto(local_clean)
                
                # Link do evento
                link_el = card.query_selector("a")
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://www.oxyscrono.com.br/{href}"
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                
                eventos.append({
                    "titulo": titulo,
                    "data": data_formatada,
                    "local": local,
                    "link": link,
                    "hash": evento_hash,
                    "fonte": "OxyScrono",
                    "data_obj": data_obj,
                    "categoria": "Evento Esportivo"
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

def extrair_oxyscrono(max_tentativas=3):
    """Extrai eventos do OxyScrono.com.br"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 OxyScrono - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                try:
                    print("📄 Carregando OxyScrono.com.br...")
                    page.goto("https://www.oxyscrono.com.br/eventos", timeout=60000)
                    time.sleep(5)
                    
                    eventos = coletar_eventos_oxyscrono(page)
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
                        
                        print(f"✅ OxyScrono: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 OxyScrono.com.br falhou após todas as tentativas")
            continue
    
    return eventos