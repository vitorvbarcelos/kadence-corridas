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

def processar_data_ativo(dia_str, mes_str):
    """Processa data do formato Ativo: dia='17', mês='Ago' -> '17/08/2025'"""
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

def carregar_todos_eventos_ativo(page, max_cliques=10):
    """Carrega todos os eventos clicando em 'Ver mais'"""
    print("🔄 Carregando todos os eventos...")
    
    cliques_realizados = 0
    cliques_sem_efeito = 0
    max_cliques_sem_efeito = 3
    
    while cliques_realizados < max_cliques and cliques_sem_efeito < max_cliques_sem_efeito:
        try:
            # Conta eventos antes do clique
            cards_antes = len(page.query_selector_all("article.card.card-event"))
            
            # Procura pelo botão "Ver mais"
            seletores_ver_mais = [
                "a.button-primary[data-per_page]",
                "a.button-primary:has-text('Ver mais')",
                ".button-primary:has-text('Ver mais')"
            ]
            
            botao_ver_mais = None
            for seletor in seletores_ver_mais:
                try:
                    botao_ver_mais = page.query_selector(seletor)
                    if botao_ver_mais and botao_ver_mais.is_visible():
                        break
                except:
                    continue
            
            if not botao_ver_mais:
                print(f"   🔍 Botão 'Ver mais' não encontrado - fim dos eventos")
                break
            
            # Scroll para o botão e clica
            try:
                botao_ver_mais.scroll_into_view_if_needed()
                time.sleep(1)
                botao_ver_mais.click()
                cliques_realizados += 1
                print(f"   👉 Clique {cliques_realizados} - Aguardando novos eventos...")
                
                # Aguarda carregar novos eventos (AJAX)
                time.sleep(4)
                
            except Exception as e:
                print(f"   ⚠️ Erro ao clicar 'Ver mais': {str(e)[:50]}...")
                cliques_sem_efeito += 1
                continue
            
            # Verifica se novos eventos foram adicionados
            cards_depois = len(page.query_selector_all("article.card.card-event"))
            
            if cards_depois > cards_antes:
                cliques_sem_efeito = 0
                print(f"   📈 {cards_depois} eventos total (+{cards_depois - cards_antes} novos)")
            else:
                cliques_sem_efeito += 1
                print(f"   ⏳ Sem novos eventos ({cliques_sem_efeito}/{max_cliques_sem_efeito})")
            
        except Exception as e:
            print(f"   ⚠️ Erro ao carregar mais eventos: {str(e)[:50]}...")
            cliques_sem_efeito += 1
            time.sleep(2)
    
    total_final = len(page.query_selector_all("article.card.card-event"))
    print(f"🏁 Carregamento finalizado: {total_final} eventos | {cliques_realizados} cliques realizados")
    return total_final

def coletar_eventos_ativo(page):
    """Coleta eventos de corrida do Ativo.com"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all("article.card.card-event")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector("h3.title.title-fixed-height")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                if not titulo:
                    continue
                
                # Data (dia e mês separados)
                dia_el = card.query_selector(".date-square-day")
                mes_el = card.query_selector(".date-square-month")
                
                if not dia_el or not mes_el:
                    continue
                
                dia_str = dia_el.inner_text().strip() if dia_el else ""
                mes_str = mes_el.inner_text().strip() if mes_el else ""
                
                data_obj, data_formatada = processar_data_ativo(dia_str, mes_str)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local
                local_el = card.query_selector(".subtitle-small.place-input")
                local = limpar_texto(local_el.inner_text()) if local_el else "Local não informado"
                
                # Link
                link_el = card.query_selector("a.card-cover.large")
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://www.ativo.com{href}"
                
                # Distâncias (opcional)
                distancias_el = card.query_selector(".distances")
                distancias = limpar_texto(distancias_el.inner_text()) if distancias_el else ""
                
                # Categoria/Tag
                tag_el = card.query_selector(".tag")
                categoria = limpar_texto(tag_el.inner_text()) if tag_el else "Corrida de Rua"
                
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
                    "fonte": "Ativo",
                    "data_obj": data_obj,
                    "categoria": categoria,
                    "distancias": distancias
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

def extrair_ativo(max_tentativas=3):
    """Extrai eventos de corrida do Ativo.com"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Ativo.com - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL do calendário do Ativo
                url = "https://www.ativo.com/calendario/"
                
                try:
                    print("📄 Carregando Ativo.com...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(5)
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector("article.card.card-event", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Carrega todos os eventos clicando em "Ver mais"
                    total_cards = carregar_todos_eventos_ativo(page, max_cliques=10)
                    
                    # Agora coleta todos os eventos de uma vez
                    print(f"🔄 Processando {total_cards} eventos...")
                    eventos = coletar_eventos_ativo(page)
                    
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
                        
                        print(f"✅ Ativo.com: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 Ativo.com falhou após todas as tentativas")
            continue
    
    return eventos