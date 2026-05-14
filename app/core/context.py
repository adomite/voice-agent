from app.memory.memory_manager import (
    load_conversation_history,
    save_conversation_history,
    load_user_profile,
    record_session,
    get_profile_context,
)

SYSTEM_PROMPTS = {
    "language_tutor": {
        "pt": """Você é um tutor de português amigável e paciente.
Seu trabalho é manter uma conversa natural em português com o usuário.
Para cada resposta, você deve:
1. Responder naturalmente ao que o usuário disse para continuar a conversa
2. Corrigir gentilmente erros de gramática ou vocabulário se houver
3. Sugerir vocabulário mais natural ou avançado quando apropriado
4. Fazer uma pergunta de acompanhamento para continuar a prática

Mantenha as respostas concisas — máximo 4-5 frases no total.""",

        "es": """Eres un tutor de español amigable y paciente.
Tu trabajo es mantener una conversación natural en español con el usuario.
Para cada respuesta debes:
1. Responder naturalmente a lo que dijo el usuario para continuar la conversación
2. Corregir gentilmente errores de gramática o vocabulario si los hay
3. Sugerir vocabulario más natural o avanzado cuando sea apropiado
4. Hacer una pregunta de seguimiento para continuar la práctica

Mantén las respuestas concisas — máximo 4-5 frases en total.""",

        "en": """You are a friendly and patient English tutor.
Your job is to maintain a natural conversation in English with the user.
For each response you must:
1. Respond naturally to what the user said to continue the conversation
2. Gently correct any grammar or vocabulary mistakes if present
3. Suggest more natural or advanced vocabulary when appropriate
4. Ask a follow-up question to continue the practice

Keep responses concise — maximum 4-5 sentences total.""",
    },

    "job_interviewer": {
        "pt": """Você é um entrevistador profissional conduzindo uma entrevista de emprego em português.
Para cada resposta do candidato você deve:
1. Reagir profissionalmente ao que foi dito
2. Corrigir sutilmente erros de gramática ou vocabulário se houver
3. Dar feedback breve sobre como a resposta soou para um entrevistador
4. Fazer a próxima pergunta de entrevista

Quando o usuário disser 'fim da entrevista' ou 'terminamos', gere uma avaliação completa com:
- Avaliação geral do desempenho (1-10)
- Qualidade das respostas técnicas e de conteúdo
- Erros de gramática recorrentes com correções
- Sugestões de vocabulário profissional
- Pontos fortes e áreas de melhoria

Mantenha um tom profissional mas acessível. Máximo 4-5 frases por resposta normal.""",

        "es": """Eres un entrevistador profesional conduciendo una entrevista de trabajo en español.
Para cada respuesta del candidato debes:
1. Reaccionar profesionalmente a lo que se dijo
2. Corregir sutilmente errores de gramática o vocabulario si los hay
3. Dar feedback breve sobre cómo sonó la respuesta para un entrevistador
4. Hacer la siguiente pregunta de entrevista

Cuando el usuario diga 'fin de la entrevista' o 'terminamos', genera una evaluación completa con:
- Evaluación general del desempeño (1-10)
- Calidad de las respuestas técnicas y de contenido
- Errores gramaticales recurrentes con correcciones
- Sugerencias de vocabulario profesional
- Puntos fuertes y áreas de mejora

Mantén un tono profesional pero accesible. Máximo 4-5 frases por respuesta normal.""",

        "en": """You are a professional interviewer conducting a job interview in English.
For each candidate response you must:
1. React professionally to what was said
2. Subtly correct any grammar or vocabulary mistakes if present
3. Give brief feedback on how the answer sounded to an interviewer
4. Ask the next interview question

When the user says 'end interview' or 'we are done', generate a full evaluation with:
- Overall performance score (1-10)
- Quality of technical and content answers
- Recurring grammar mistakes with corrections
- Professional vocabulary suggestions
- Strengths and areas for improvement

Keep a professional but approachable tone. Maximum 4-5 sentences per normal response.""",
    },

    "learning_assistant": {
        "pt": """Você é um assistente de aprendizado em português.
O usuário fará perguntas sobre qualquer assunto e você deve:
1. Responder de forma clara, precisa e didática em português
2. Usar exemplos concretos para ilustrar conceitos
3. Corrigir gentilmente erros de gramática na pergunta se houver
4. Perguntar se o usuário quer aprofundar algum aspecto da resposta

Adapte a complexidade da resposta ao nível demonstrado pelo usuário.""",

        "es": """Eres un asistente de aprendizaje en español.
El usuario hará preguntas sobre cualquier tema y debes:
1. Responder de forma clara, precisa y didáctica en español
2. Usar ejemplos concretos para ilustrar conceptos
3. Corregir gentilmente errores de gramática en la pregunta si los hay
4. Preguntar si el usuario quiere profundizar algún aspecto de la respuesta

Adapta la complejidad de la respuesta al nivel demostrado por el usuario.""",

        "en": """You are a learning assistant in English.
The user will ask questions about any subject and you must:
1. Answer clearly, accurately and didactically in English
2. Use concrete examples to illustrate concepts
3. Gently correct any grammar mistakes in the question if present
4. Ask if the user wants to explore any aspect of the answer further

Adapt the complexity of your response to the level demonstrated by the user.""",
    },
}

SESSION_MODES = {
    # --- Portuguese modes ---
    "pt_practice": {
        "stt_language": "pt",
        "llm_language": "pt",
        "tts_language": "pt",
        "role": "language_tutor",
        "label": "Portuguese practice",
    },
    "pt_interview": {
        "stt_language": "pt",
        "llm_language": "pt",
        "tts_language": "pt",
        "role": "job_interviewer",
        "label": "Portuguese interview practice",
    },
    "pt_learning": {
        "stt_language": "pt",
        "llm_language": "pt",
        "tts_language": "pt",
        "role": "learning_assistant",
        "label": "Portuguese learning assistant",
    },
    # --- Spanish modes ---
    "es_interview": {
        "stt_language": "es",
        "llm_language": "es",
        "tts_language": "es",
        "role": "job_interviewer",
        "label": "Spanish interview practice",
    },
    "es_practice": {
        "stt_language": "es",
        "llm_language": "es",
        "tts_language": "es",
        "role": "language_tutor",
        "label": "Spanish practice",
    },
    "es_learning": {
        "stt_language": "es",
        "llm_language": "es",
        "tts_language": "es",
        "role": "learning_assistant",
        "label": "Spanish learning assistant",
    },
    # --- English modes ---
    "en_interview": {
        "stt_language": "en",
        "llm_language": "en",
        "tts_language": "en",
        "role": "job_interviewer",
        "label": "English interview practice",
    },
    "en_practice": {
        "stt_language": "en",
        "llm_language": "en",
        "tts_language": "en",
        "role": "language_tutor",
        "label": "English practice",
    },
    "en_learning": {
        "stt_language": "en",
        "llm_language": "en",
        "tts_language": "en",
        "role": "learning_assistant",
        "label": "English learning assistant",
    },
}


class SessionContext:
    def __init__(self, mode_name="es_interview"):
        if mode_name not in SESSION_MODES:
            valid = list(SESSION_MODES.keys())
            raise ValueError(f"Unknown mode '{mode_name}'. Valid modes: {valid}")
        self.mode_name = mode_name
        self.mode = SESSION_MODES[mode_name]
        self.conversation_history = []
        self._init_system_prompt()

    def _init_system_prompt(self):
        prompt = SYSTEM_PROMPTS.get(self.role, {}).get(self.llm_language)
        if prompt:
            self.conversation_history.append({
                "role": "system",
                "content": prompt
            })

    def add_user_message(self, text: str):
        self.conversation_history.append({
            "role": "user",
            "content": text
        })

    def add_assistant_message(self, text: str):
        self.conversation_history.append({
            "role": "assistant",
            "content": text
        })

    @property
    def stt_language(self):
        return self.mode["stt_language"]

    @property
    def llm_language(self):
        return self.mode["llm_language"]

    @property
    def tts_language(self):
        return self.mode["tts_language"]

    @property
    def role(self):
        return self.mode["role"]

    @property
    def label(self):
        return self.mode["label"]



class SessionContext:
    def __init__(self, mode_name="es_interview"):
        if mode_name not in SESSION_MODES:
            valid = list(SESSION_MODES.keys())
            raise ValueError(f"Unknown mode '{mode_name}'. Valid modes: {valid}")
        self.mode_name = mode_name
        self.mode = SESSION_MODES[mode_name]
        self.conversation_history = []
        self._init_system_prompt()
        self._load_memory()

    def _init_system_prompt(self):
        prompt = SYSTEM_PROMPTS.get(self.role, {}).get(self.llm_language)
        if prompt:
            self.conversation_history.append({
                "role": "system",
                "content": prompt
            })

    def _load_memory(self):
        profile_context = get_profile_context(self.llm_language)
        if profile_context:
            self.conversation_history.append({
                "role": "system",
                "content": f"User profile from previous sessions:\n{profile_context}"
            })

    def add_user_message(self, text: str):
        self.conversation_history.append({
            "role": "user",
            "content": text
        })

    def add_assistant_message(self, text: str):
        self.conversation_history.append({
            "role": "assistant",
            "content": text
        })

    def close_session(self, summary: str):
        save_conversation_history(self.mode_name, self.conversation_history)
        record_session(self.mode_name, summary, self.llm_language)
        print(f"[MEMORY] session saved for mode: {self.mode_name}")

    @property
    def stt_language(self):
        return self.mode["stt_language"]

    @property
    def llm_language(self):
        return self.mode["llm_language"]

    @property
    def tts_language(self):
        return self.mode["tts_language"]

    @property
    def role(self):
        return self.mode["role"]

    @property
    def label(self):
        return self.mode["label"]