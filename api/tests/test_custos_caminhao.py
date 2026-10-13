from app.services.viagem_caminhao import comparar_custos


def rota(km,minutos,pedagio,pendentes=0):
    return {'distancia_km':km,'tempo_min':minutos,'infraestrutura':{
        'pedagios':{'subtotal_conhecido_reais':pedagio,'tarifas_pendentes':pendentes}}}


def test_desvio_mais_caro_reduz_economia_e_inclui_atraso_contratual():
    resultado=comparar_custos(rota(10,30,10),rota(20,90,30),{
        'custo_por_km':5,'custo_hora_motorista':30,'custo_operacional_veiculo_hora':30,
        'custo_atraso_hora':120,'prejuizo_potencial_alagamento':300},True,janela_min=60)
    # 50 de km + 60 de operacao + 20 de pedagios + 60 de atraso.
    assert resultado['custo_desvio_brl']==190
    assert resultado['economia_liquida_potencial_brl']==110


def test_tarifa_ausente_nunca_torna_comparacao_confirmada():
    resultado=comparar_custos(rota(10,30,0,1),rota(10,30,0,2),{},False)
    assert resultado['tarifas_pendentes_comparacao']==3
    assert resultado['comparacao_completa'] is False
    assert resultado['prejuizo_potencial_evitado_brl']==0
