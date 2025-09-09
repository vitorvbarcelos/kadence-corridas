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

def processar_data_liverun(data_str):
    """Processa data do LIVE! Run: '14/09 - Domingo' -> '14/09/2025'"""
    if not data_str:
        return None, None
    
    try:
        # Extrai apenas a parte da data: "14/09"
        data_match = re.search(r'(\d{1,2})/(\d{1,2})', data_str)
        if not data_match:
            return None, None
        
        dia = data_match.group(1).zfill(2)
        mes = data_match.group(2).zfill(2)
        
        # Assume ano atual ou próximo
        ano_atual = datetime.now().year
        data_str_formatada = f"{dia}/{mes}/{ano_atual}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            # Se a data já passou, assume ano seguinte
            if data_obj < datetime.now():
                data_obj = datetime.strptime(f"{dia}/{mes}/{ano_atual + 1}", '%d/%m/%Y')
                data_str_formatada = f"{dia}/{mes}/{ano_atual + 1}"
            
            return data_obj, data_str_formatada
        except ValueError:
            pass
    except:
        pass
    
    return None, None

def coletar_eventos_liverun(page):
    """Coleta eventos do LIVE! Run disponíveis"""
    eventos = []
    
    try:
        # Scroll para carregar todos os eventos
        print("   🔄 Carregando todos os eventos...")
        for i in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
        
        # Seleciona todos os eventos disponíveis (não encerrados)
        eventos_cards = page.query_selector_all(".event:not(:has(.subscription-closed))")
        print(f"   📦 {len(eventos_cards)} eventos disponíveis encontrados")
        
        for i, card in enumerate(eventos_cards):
            try:
                # Link do evento
                link_el = card.query_selector("a")
                if not link_el:
                    continue
                
                href = link_el.get_attribute("href")
                if not href:
                    continue
                
                url_evento = href if href.startswith("http") else f"https://www.liverun.com.br/{href}"
                
                # Cidade/local
                cidade_el = card.query_selector(".event-info h3")
                if not cidade_el:
                    continue
                
                cidade = limpar_texto(cidade_el.inner_text())
                if not cidade or len(cidade) < 3:
                    continue
                
                # Data do evento
                data_el = card.query_selector(".event-date")
                if not data_el:
                    continue
                
                data_str = limpar_texto(data_el.inner_text())
                data_obj, data_formatada = processar_data_liverun(data_str)
                
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Modalidades
                modalidades_el = card.query_selector(".event-modalities")
                modalidades = "Corrida de Rua"
                if modalidades_el:
                    mod_text = limpar_texto(modalidades_el.inner_text())
                    if mod_text:
                        modalidades = mod_text
                
                # Título do evento (LIVE! Run + Cidade)
                titulo = f"LIVE! Run {cidade} 2025"
                
                # Status do botão (verifica se está disponível)
                btn_el = card.query_selector(".btn-two")
                disponivel = True
                if btn_el:
                    btn_text = limpar_texto(btn_el.inner_text())
                    if "encerrad" in btn_text.lower() or "breve" in btn_text.lower():
                        disponivel = False
                
                # Só adiciona se estiver disponível
                if not disponivel:
                    continue
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo, data_formatada, cidade)
                
                eventos.append({
                    "titulo": titulo,
                    "data": data_formatada,
                    "local": cidade,
                    "link": url_evento,
                    "hash": evento_hash,
                    "fonte": "LIVE! Run",
                    "data_obj": data_obj,
                    "categoria": "Corrida de Rua",
                    "modalidade": modalidades
                })
                
                # Mostra detalhes dos primeiros 3 eventos
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo} | {data_formatada} | {cidade}")
                
            except Exception as e:
                continue
        
        print(f"   🎯 Total de eventos válidos coletados: {len(eventos)}")
        
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_liverun(max_tentativas=3):
    """Extrai eventos do LIVE! Run"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 LIVE! Run - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                try:
                    print("📄 Carregando LIVE! Run...")
                    page.goto("https://www.liverun.com.br/calendario", timeout=60000)
                    time.sleep(5)
                    
                    # Aguarda os eventos aparecerem
                    try:
                        page.wait_for_selector(".event", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Eventos não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    eventos = coletar_eventos_liverun(page)
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
                        
                        print(f"✅ LIVE! Run: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 LIVE! Run falhou após todas as tentativas")
            continue
    
    return eventos