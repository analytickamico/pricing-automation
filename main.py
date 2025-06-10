import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import logging
import requests
from dotenv import load_dotenv
import numpy as np
from os import path
import time
import os

logging.basicConfig(level=logging.INFO)
pricing_logger = logging.getLogger(__name__)
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
client = gspread.authorize(creds)

def enviar_dados(df: pd.DataFrame, sheet_name: str, sheet_url: str):
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        client = gspread.authorize(creds)

        if 'sku_seller' in df.columns:
            df['sku_seller'] = df['sku_seller'].astype(str).str.strip()

        pricing_logger.info(f"Enviando dataframe '{sheet_name}':\n{df.head().to_string()}")

        spreadsheet = client.open_by_url(sheet_url)
        sheet = spreadsheet.worksheet(sheet_name)

        values = [df.columns.tolist()] + df.values.tolist()
        end_col = chr(64 + df.shape[1])
        end_row = len(values)
        range_to_update = f"A1:{end_col}{end_row}"

        sheet.batch_update([{
            "range": range_to_update,
            "values": values
        }])

        if 'sku_seller' in df.columns:
            sku_seller_col_index = df.columns.get_loc('sku_seller') + 1
            sheet.format(f"{chr(64 + sku_seller_col_index)}2:{chr(64 + sku_seller_col_index)}", {
                "numberFormat": {"type": "TEXT"}
            })

        pricing_logger.info(f"Dados escritos com sucesso na aba '{sheet_name}' da planilha {sheet_url}")

    except Exception as e:
        pricing_logger.exception(f"Erro ao atualizar a aba '{sheet_name}': {str(e)}")
        raise
    
def ler_dados(sheet_url: str, sheet_name: str, max_retries: int = 3) -> pd.DataFrame:
    for attempt in range(max_retries):
        try:
            pricing_logger.info(f"Attempting to open sheet URL: {sheet_url}")
            spreadsheet = client.open_by_url(sheet_url)
            pricing_logger.info(f"Successfully opened spreadsheet. Accessing worksheet: {sheet_name}")
            sheet = spreadsheet.worksheet(sheet_name)
            pricing_logger.info(f"Retrieving all values from worksheet")
            all_values = sheet.get_all_values()
            if not all_values:
                pricing_logger.warning(f"Sheet '{sheet_name}' está vazia")
                return pd.DataFrame()

            headers = all_values[0]
            data = all_values[1:] if len(all_values) > 1 else []
            df = pd.DataFrame(data, columns=headers)
            pricing_logger.info(f"Lendo sheet '{sheet_name}' da url {sheet_url}. Linhas iniciais: {len(df)}, Colunas: {df.columns.tolist()}")

            if df.empty:
                pricing_logger.warning(f"Sheet '{sheet_name}' não contém dados")
                return df

            df = df[df.apply(lambda row: not all(str(val).strip() == '' for val in row), axis=1)]
            pricing_logger.info(f"Filtrando linhas vazias. {len(df)} Linhas restantes")

            if df.empty:
                pricing_logger.warning(f"Não Foram encontradas linhas vazias na aba '{sheet_name}'.")
                return df

            numeric_columns = [
                'preco_atual_hairpro', 'preco_minimo', 'segundo_preco_minimo',
                'preco_para_buybox', 'preco_buybox_atual', 'PDV'
            ]
            numeric_cols = [col for col in numeric_columns if col in df.columns]

            for col in numeric_cols:
                try:
                    df[col] = df[col].astype(str).str.replace(r'R\$\s*', '', regex=True).str.replace(',', '.', regex=False).str.strip()
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    pricing_logger.info(f"Column '{col}' converted to float.")
                except Exception as e:
                    pricing_logger.error(f"Error converting column '{col}' to float: {str(e)}")
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            if numeric_cols and df[numeric_cols].isna().any().any():
                pricing_logger.warning(f"Some values in columns {numeric_cols} were converted to NaN due to invalid data.")

            pricing_logger.info(f"Final DataFrame:\n{df.head().to_string(index=False)}")
            return df

        except ConnectionError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                pricing_logger.warning(f"Connection error: {str(e)}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                pricing_logger.error(f"Failed to read sheet '{sheet_name}' after {max_retries} attempts: {str(e)}")
                raise

def calcular_buybox(lojas=['HAIRPRO', 'Hair Pro Cosméticos']):
    start_time = time.time()
    results = []
    
    try:
        # Requisição à API
        response = requests.get("https://www.price.kamico.com.br/api/products/")
        response.raise_for_status()  # Levanta exceção para códigos de status HTTP 4xx/5xx
        data = response.json()
        
        # Verifica se a resposta é uma lista ou dicionário
        if not isinstance(data, (list, dict)):
            pricing_logger.error("Resposta da API não está no formato esperado (lista ou dicionário).")
            return pd.DataFrame(), pd.DataFrame()
        
        # Converte para lista se for dicionário
        df = pd.DataFrame(data if isinstance(data, list) else [data])
        
        # Verifica se as colunas necessárias existem
        required_columns = ['sku', 'loja', 'preco_final', 'descricao', 'marketplace', 'status']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            pricing_logger.error(f"Colunas faltando na resposta da API: {missing_columns}")
            return pd.DataFrame(), pd.DataFrame()
        
        # Seleciona apenas as colunas necessárias
        df=df[df['status']=='ativo']
        df = df[required_columns].copy()
        
        # Converte preco_final para numérico
        df['preco_final'] = pd.to_numeric(df['preco_final'], errors='coerce')
        
        # Verifica se todos os preços são inválidos
        if df['preco_final'].isna().all():
            pricing_logger.error("Todos os valores de preco_final são inválidos.")
            return pd.DataFrame(), df
        
        # Remove linhas com preços inválidos e loga aviso
        if df['preco_final'].isna().any():
            pricing_logger.warning("Alguns preços foram ignorados devido a valores inválidos.")
            df = df.dropna(subset=['preco_final'])
        
        # Filtra SKUs das lojas especificadas
        hairpro_skus = df[df['loja'].isin(lojas)]['sku'].unique()
        
        for sku in hairpro_skus:
            group = df[df['sku'] == sku]
            if len(group['preco_final']) < 2:
                pricing_logger.warning(f"SKU {sku}: Não há preços suficientes para comparação.")
                continue
            
            # Ordena preços e obtém o menor e o segundo menor
            precos_ordenados = group['preco_final'].sort_values()
            min_price = precos_ordenados.iloc[0]
            second_min_price = precos_ordenados.iloc[1]
            buybox_loja = group.loc[group['preco_final'] == min_price, 'loja'].iloc[0]
            
            # Processa cada loja da lista
            for loja in lojas:
                hairpro_row = group[group['loja'] == loja]
                if hairpro_row.empty:
                    continue
                
                preco_hairpro = hairpro_row['preco_final'].iloc[0]
                descricao = hairpro_row['descricao'].iloc[0]
                marketplace = hairpro_row['marketplace'].iloc[0]
                status = hairpro_row['status'].iloc[0]
                
                if preco_hairpro == min_price:
                    adjusted_price = max(second_min_price - 0.10, 0.01)  # Evita preços negativos
                    status_buybox = "Ganhando buybox"
                else:
                    adjusted_price = max(min_price - 0.10, 0.01)  # Evita preços negativos
                    status_buybox = "Perdendo buybox"
                
                results.append({
                    'sku_seller': sku,
                    'loja': loja,
                    'descricao': descricao,
                    'preco_atual_hairpro': preco_hairpro,
                    'preco_minimo': min_price,
                    'segundo_preco_minimo': second_min_price,
                    'preco_para_buybox': adjusted_price,
                    'vencedor_buybox': buybox_loja,
                    'preco_buybox_atual': min_price,
                    'status_buybox': status_buybox,
                    'marketplace': marketplace,
                    'status': status
                })
        
        result_df = pd.DataFrame(results)
        pricing_logger.info(f"Preços ajustados calculados em {time.time() - start_time:.2f} segundos.")
        return result_df, df
    
    except requests.exceptions.RequestException as e:
        pricing_logger.error(f"Erro na requisição à API: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        pricing_logger.error(f"Erro ao processar dados: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

df_scrap = calcular_buybox()[0]
df_scrap_blz=df_scrap[df_scrap['marketplace']=='Beleza na Web']
df_scrap_blz=df_scrap_blz[df_scrap_blz['status']=='ativo']

base_url = 'https://api.anymarket.com.br'
anymarket_cred_path = path.join(os.getcwd(), '.env') 

MARKETPLACE_IDS = {
    "BELEZA_NA_WEB": "287287989",
    "MERCADO_LIVRE": "275387715"
}

class AnymarketAPI:
    def __init__(
        self,
        base_url: str = base_url,
        credentials_path: str = anymarket_cred_path,
        marketplace_ids: dict = MARKETPLACE_IDS
    ):
        self.base_url = base_url
        self.marketplace_ids = marketplace_ids
        load_dotenv(credentials_path)
        self.gumga_token = os.getenv("GUMGA_TOKEN")
        if not self.gumga_token:
            raise ValueError("GUMGA_TOKEN não encontrado no arquivo .env")
        
        self.headers = {
            "Content-Type": "application/json",
            "gumgaToken": self.gumga_token
        }

    def retorna_id(self, sku: str) -> dict:
        url = f"{self.base_url}/v2/products?sku={sku}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return {
                "sku": sku,
                "status_code": response.status_code,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "sku": sku,
                "status_code": getattr(e.response, 'status_code', None),
                "error": str(e)
            }
    
    def manual_pricing(self, product_id: str) -> dict:
        try:
            payload = {
                'calculatedPrice': False,
                'definitionPriceScope': 'SKU_MARKETPLACE',
            }
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/merge-patch+json'
            url = f"{self.base_url}/v2/products/{product_id}"
            response = requests.patch(url, headers=headers, json=payload)
            response.raise_for_status()
            return {
                "id": product_id,
                "status_code": response.status_code,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "id": product_id,
                "status_code": getattr(e.response, 'status_code', None),
                "error": str(e)
            }

    def retorna_skuid_marketplaces(self, partner_id: str, marketplace: str) -> dict:
        url = f"{self.base_url}/v2/skus/marketplaces?partnerID={partner_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json() if isinstance(response.json(), list) else response.json().get('data', [])
            for mktplace in data:
                if mktplace.get('marketPlace') == marketplace:
                    skuid_marketplace = mktplace.get('id')
                    return {
                        "partner_id": partner_id,
                        "marketplace": marketplace,
                        "status_code": response.status_code,
                        "data": {"skuid_marketplace": skuid_marketplace}
                    }
            return {
                "partner_id": partner_id,
                "marketplace": marketplace,
                "status_code": response.status_code,
                "error": f"Marketplace {marketplace} não encontrado para partnerID {partner_id}"
            }
        except requests.exceptions.RequestException as e:
            return {
                "partner_id": partner_id,
                "marketplace": marketplace,
                "status_code": getattr(e.response, 'status_code', None),
                "error": str(e)
            }
            
    def get_sku_marketplace_by_id(self, sku_id: str, marketplace_id: str) -> dict:
        url = f"{self.base_url}/v2/skus/{sku_id}/marketplaces/{marketplace_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return {
                "sku": sku_id,
                "marketplace_id": marketplace_id,
                "status_code": response.status_code,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "sku": sku_id,
                "marketplace_id": marketplace_id,
                "status_code": getattr(e.response, 'status_code', None),
                "error": str(e)
            }
    
    def update_sku_marketplace(self, sku_id: str, marketplace_id: str, price: float, title: str, discount_price: float = None, ean: str = None) -> dict:
        url = f"{self.base_url}/v2/skus/{sku_id}/marketplaces/{marketplace_id}"
        try:
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/json'
            payload = {
                "price": price,
            }
            if discount_price is not None:
                payload["discountPrice"] = discount_price
                payload["fields"]["DISCOUNT_VALUE"] = str(round(price - discount_price, 2))
            if ean is not None:
                payload["fields"]["EAN"] = ean
            response = requests.put(url, headers=headers, json=payload)
            response.raise_for_status()
            return {
                "sku": sku_id,
                "marketplace_id": marketplace_id,
                "status_code": response.status_code,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "sku": sku_id,
                "marketplace_id": marketplace_id,
                "status_code": getattr(e.response, 'status_code', None),
                "error": str(e)
            }
        
    def update_price(self, ad_id: str, new_price: float, promo_price : float) -> dict:
        """Faz uma requisição PUT para atualizar o preço de um SKU em um marketplace."""
        # Valida se o preço tem no máximo 2 casas decimais
        if round(new_price, 2) != new_price:
            return {
                "ad_id": ad_id,
                "status_code": None,
                "error": f"New Price {new_price} must have at most 2 decimal places"
            }

        url = f"{self.base_url}/v2/skus/marketplaces/prices"
        try:
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/json'

            payload = [{
                "id": ad_id,
                "price": promo_price,
                "discountPrice": new_price 
            }]

            response = requests.put(url, headers=headers, json=payload)
            response.raise_for_status()
            
            return {
                "ad_id": ad_id,
                "status_code": response.status_code,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "ad_id": ad_id,
                "status_code": getattr(e.response, 'status_code', None),
                "error": str(e)
            }

def main_job():
    """Função principal que executa a lógica do código original."""
    try:
        # Calculate buybox and get the scraped dataframe
        df_scrap = calcular_buybox()[0]
        df_scrap=df_scrap[df_scrap['marketplace']=='Beleza na Web']
        df_scrap=df_scrap[df_scrap['status']=='ativo']

        pdv_blz = ler_dados('https://docs.google.com/spreadsheets/d/1u7dCTQzbqgKSSjpSVtsUl7ea2j2YgW4Ko2nB9akE1ws/edit?gid=1486126181#gid=1486126181','PDV beleza na web')

        pdv_blz_fil=pdv_blz[['sku_beleza','PDV','SKU','STATUS','MARKETPLACE']].dropna(subset=['SKU','PDV','sku_beleza'])

        df_scrap_pdv_blz = pd.merge(df_scrap_blz, pdv_blz_fil, left_on='sku_seller', right_on='sku_beleza', how='left')

        df_pricing = df_scrap_pdv_blz[df_scrap_pdv_blz['STATUS'] == "ATIVO"]
        df_pricing['preco-regra'] = np.where(
            (df_pricing['PDV'].notnull()) & (df_pricing['preco_para_buybox'].notnull()) & (df_pricing['PDV'] < df_pricing['preco_para_buybox']),
            df_pricing['preco_para_buybox'],
            df_pricing['PDV']
        )
        df_pricing = df_pricing[df_pricing["STATUS"] == "ATIVO"]
        df_pricing['preco-de'] = (df_pricing['preco-regra'] * 1.42).round(2)

        # Drop rows with NaN values
        df_pricing = df_pricing.dropna()
        df_pricing['preco-regra']=df_pricing['preco-regra'].round(2)
        # Initialize Anymarket API
        api = AnymarketAPI()

        # Update prices via API
        for index, row in df_pricing.iterrows():
            skuid = api.retorna_id(row['SKU'])
            api.manual_pricing(skuid['data']['content'][0]['id'])
            skuid_marketplace = api.retorna_skuid_marketplaces(partner_id=row['SKU'], marketplace=row['MARKETPLACE'])
            api.update_price(ad_id=skuid_marketplace['data']['skuid_marketplace'], new_price=row['preco-regra'], promo_price=row['preco-de'])
            # Adicionar print com SKU, preço de e preço regra
            print(f"SKU {row['SKU']} alterado: preço regra = {row['preco-regra']}, preço de = {row['preco-de']}")
            
        pricing_logger.info("Ciclo de execução concluído com sucesso.")
    except Exception as e:
        pricing_logger.error(f"Erro na execução do ciclo: {str(e)}")

if __name__ == "__main__":
    main_job()
