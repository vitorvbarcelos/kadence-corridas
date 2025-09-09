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

def processar_data_trackfield(data_str):
    """Processa data do Track&Field: '27 de jul' -> '27/07/2025'"""
    if not data_str:
        return None, None
    
    try:
        # Mapeia meses em português
        meses = {
            'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
            'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
            'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
        }
        
        # Regex para capturar "27 de jul"
        match = re.search(r'(\d{1,2})\s+de\s+(\w{3})', data_str.lower())
        if not match:
            return None, None
        
        dia = match.group(1).zfill(2)
        mes_texto = match.group(2)
        
        if mes_texto not in meses:
            return None, None
        
        mes_num = meses[mes_texto]
        
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
    
    return None, None

def carregar_mais_eventos(page, max_cliques=10):
    """Clica no botão 'carregar mais provas' para carregar todos os eventos"""
    cliques = 0
    
    while cliques < max_cliques:
        try:
            # Procura pelo botão "carregar mais provas"
            botao = page.query_selector("button:has-text('carregar mais provas')")
            
            if not botao:
                print(f"   📝 Botão não encontrado após {cliques} cliques")
                break
            
            # Verifica se está habilitado
            disabled = botao.get_attribute("disabled")
            if disabled is not None:
                print(f"   📝 Botão desabilitado após {cliques} cliques")
                break
            
            # Clica no botão
            botao.click()
            cliques += 1
            print(f"   🔄 Clique {cliques} - Carregando mais eventos...")
            
            # Aguarda carregamento
            time.sleep(3)
            
        except Exception as e:
            print(f"   ⚠️ Erro ao clicar no botão: {str(e)[:50]}...")
            break
    
    print(f"   ✅ Carregamento concluído após {cliques} cliques")
    return cliques

def coletar_eventos_trackfield(page):
    """Coleta eventos do Track&Field Run Series"""
    eventos = []
    
    try:
        # Primeiro, carrega todos os eventos clicando no botão
        carregar_mais_eventos(page, max_cliques=15)
        
        # Aguarda um pouco mais para garantir carregamento
        time.sleep(3)
        
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".run-series-card")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Local com ícone 📍
                local_el = card.query_selector("a:has-text('📍')")
                if not local_el:
                    continue
                
                local_text = limpar_texto(local_el.inner_text())
                # Remove o emoji 📍 e limpa
                local = re.sub(r'^📍\s*', '', local_text).strip()
                
                if not local or len(local) < 3:
                    continue
                
                # Título do evento
                titulo_el = card.query_selector("h2 a")
                if not titulo_el:
                    continue
                
                titulo = limpar_texto(titulo_el.inner_text())
                if not titulo or len(titulo) < 5:
                    continue
                
                # Data do evento
                data_el = card.query_selector("strong")
                if not data_el:
                    continue
                
                data_str = limpar_texto(data_el.inner_text())
                data_obj, data_formatada = processar_data_trackfield(data_str)
                
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Link do evento
                link_el = card.query_selector("h2 a")
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://www.tfsports.com.br{href}"
                
                # Título completo (Track&Field Run Series + Local)
                titulo_completo = f"Track&Field Run Series {titulo}"
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo_completo, data_formatada, local)
                
                eventos.append({
                    "titulo": titulo_completo,
                    "data": data_formatada,
                    "local": local,
                    "link": link,
                    "hash": evento_hash,
                    "fonte": "Track&Field",
                    "data_obj": data_obj,
                    "categoria": "Corrida de Rua",
                    "modalidade": "Corrida de Rua"
                })
                
                # Mostra detalhes dos primeiros 3 eventos
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo_completo[:40]}... | {data_formatada} | {local}")
                
            except Exception as e:
                continue
        
        print(f"   🎯 Total de eventos válidos coletados: {len(eventos)}")
        
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_trackfield(max_tentativas=3):
    """Extrai eventos do Track&Field Run Series"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Track&Field Run Series - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                try:
                    print("📄 Carregando Track&Field Run Series...")
                    page.goto("https://www.tfsports.com.br/run-series/", timeout=60000)
                    time.sleep(8)  # Site Next.js precisa de mais tempo
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector(".run-series-card", timeout=30000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    eventos = coletar_eventos_trackfield(page)
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
                        
                        print(f"✅ Track&Field: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 Track&Field Run Series falhou após todas as tentativas")
            continue
    
    return eventos