"""RNF-01 — Acessibilidade.

Cenário da Tabela 2 do documento de arquitetura: "Realizar comunicação
apenas com língua de sinais através do Raspberry Pi" → comunicação
independente de condições físicas. A partir apenas de gestos, o sistema
produz o texto na interface E o áudio na síntese de voz — a saída dupla do
Fluxograma 2 (Seção 7.6).
"""
import time

from libras.demo import make_demo_components
from libras.pipeline import PipelineState, TranslationPipeline
from libras.temporal import WordAssembler
from libras.tts import AsyncSpeaker, NullEngine, create_engine


def test_comunicacao_apenas_por_sinais_gera_texto_e_voz(fast_config):
    """Entrada: somente gestos. Saída: texto na tela e voz no TTS."""
    source, extractor, classifier = make_demo_components(
        fast_config, text="OI MUNDO", loop=False)
    engine = NullEngine()
    state = PipelineState()
    pipeline = TranslationPipeline(source, extractor, classifier, fast_config,
                                   state=state, on_word=engine.speak)
    for _ in range(400):
        pipeline.step()
        if len(state.to_dict()["historico"]) >= 2:
            break

    snapshot = state.to_dict()
    assert snapshot["historico"] == ["OI", "MUNDO"]  # saída em texto (tela)
    assert engine.spoken == ["OI", "MUNDO"]          # saída em voz (TTS)


def test_palavra_fecha_apos_pausa_e_buffer_limpa():
    words = []
    assembler = WordAssembler(word_pause_frames=5, on_word=words.append)
    for letter in "OLA":
        assembler.add_letter(letter)
    assert assembler.current_word == "OLA"
    for _ in range(4):
        assert assembler.tick(hand_present=False) is None
    assert assembler.tick(hand_present=False) == "OLA"
    assert words == ["OLA"]
    assert assembler.current_word == ""


def test_pausa_sem_conteudo_nao_gera_palavra_vazia():
    assembler = WordAssembler(word_pause_frames=3)
    for _ in range(10):
        assert assembler.tick(hand_present=False) is None
    assert assembler.history == []


def test_sintese_nao_bloqueia_o_laco_de_captura():
    """speak() deve retornar imediatamente mesmo com um motor lento."""
    class SlowEngine(NullEngine):
        def speak(self, text):
            time.sleep(0.3)  # simula a latência de um motor de TTS real
            super().speak(text)

    engine = SlowEngine()
    speaker = AsyncSpeaker(engine)
    t0 = time.perf_counter()
    speaker.speak("LIBRAS")
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1, f"speak() bloqueou o chamador por {elapsed:.3f}s"

    deadline = time.time() + 2.0
    while time.time() < deadline and not engine.spoken:
        time.sleep(0.01)
    speaker.close()
    assert engine.spoken == ["LIBRAS"]


def test_fallback_de_tts_sempre_disponivel(monkeypatch):
    """Sem nenhum motor de áudio disponível, a fábrica degrada para o motor
    nulo e o sistema segue funcionando (saída em texto)."""
    import libras.tts as tts_mod

    def unavailable(self, *args, **kwargs):
        raise RuntimeError("motor indisponível")

    monkeypatch.setattr(tts_mod.Pyttsx3Engine, "__init__", unavailable)
    monkeypatch.setattr(tts_mod.EspeakEngine, "__init__", unavailable)

    engine = create_engine()
    assert isinstance(engine, NullEngine)
    engine.speak("TESTE")
    assert engine.spoken == ["TESTE"]
