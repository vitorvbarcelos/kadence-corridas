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

def processar_data_corridao(dia_str, mes_str):
    """Processa data do formato Corridão: dia='09', mês='Ago' -> '09/08/2025'"""
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
        
        # Assume ano atual ou próximo
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

def fazer_scroll_completo(page, max_scrolls=50):
    """Faz scroll até o final da página para carregar todos os eventos"""
    print("🔄 Fazendo scroll para carregar todos os eventos...")
    
    scroll_realizados = 0
    eventos_anteriores = 0
    tentativas_sem_novos = 0
    max_tentativas_sem_novos = 5
    
    while scroll_realizados < max_scrolls and tentativas_sem_novos < max_tentativas_sem_novos:
        try:
            # Conta eventos atuais
            cards_atuais = len(page.query_selector_all("a.borda-banner"))
            
            # Scroll para baixo
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)  # Aguarda carregar novos eventos
            
            # Conta eventos após scroll
            cards_novos = len(page.query_selector_all("a.borda-banner"))
            
            if cards_novos > eventos_anteriores:
                eventos_anteriores = cards_novos
                tentativas_sem_novos = 0
                print(f"   📈 Scroll {scroll_realizados + 1}: {cards_novos} eventos carregados")
            else:
                tentativas_sem_novos += 1
                print(f"   ⏳ Scroll {scroll_realizados + 1}: Sem novos eventos ({tentativas_sem_novos}/{max_tentativas_sem_novos})")
            
            scroll_realizados += 1
            
        except Exception as e:
            print(f"   ⚠️ Erro no scroll {scroll_realizados + 1}: {str(e)[:50]}...")
            break
    
    total_final = len(page.query_selector_all("a.borda-banner"))
    print(f"🏁 Scroll finalizado: {total_final} eventos carregados | {scroll_realizados} scrolls realizados")
    return total_final

def coletar_eventos_corridao(page):
    """Coleta eventos de corrida do Corridão.com"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all("a.borda-banner")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector(".infotitulo")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                if not titulo:
                    continue
                
                # Data (dia e mês separados)
                dia_el = card.query_selector(".infodia")
                mes_el = card.query_selector(".infomes")
                
                if not dia_el or not mes_el:
                    continue
                
                dia_str = dia_el.inner_text().strip() if dia_el else ""
                mes_str = mes_el.inner_text().strip() if mes_el else ""
                
                data_obj, data_formatada = processar_data_corridao(dia_str, mes_str)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local
                local_el = card.query_selector(".infolocalcity")
                local = limpar_texto(local_el.inner_text()) if local_el else "Local não informado"
                
                # Link
                href = card.get_attribute("href")
                link = ""
                if href:
                    link = href if href.startswith("http") else f"https://www.corridao.com.br{href}"
                
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
                    "fonte": "Corridao",
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

def extrair_corridao(max_tentativas=3):
    """Extrai eventos de corrida do Corridão.com"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Corridão.com - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL do Corridão
                url = "https://www.corridao.com.br/"
                
                try:
                    print("📄 Carregando Corridão.com...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(5)
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector("a.borda-banner", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Faz scroll completo para carregar todos os eventos
                    total_cards = fazer_scroll_completo(page, max_scrolls=50)
                    
                    # Agora coleta todos os eventos de uma vez
                    print(f"🔄 Processando {total_cards} eventos...")
                    eventos = coletar_eventos_corridao(page)
                    
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
                        
                        print(f"✅ Corridão.com: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 Corridão.com falhou após todas as tentativas")
            continue
    
    return eventos