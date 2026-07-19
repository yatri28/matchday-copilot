"""Multilingual assistance.

When the GenAI backend is available, it answers natively in the fan's
language. This module supplies (a) the supported-language registry and
(b) localized templates the offline assistant uses so the app remains
multilingual even with no API key configured.
"""

LANGUAGES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "ar": "العربية",
    "pt": "Português",
    "de": "Deutsch",
    "hi": "हिन्दी",
}

# Minimal phrase templates for the offline assistant. {x} slots are
# filled by service output (already language-neutral labels).
PHRASES = {
    "greeting": {
        "en": "Welcome to the stadium! How can I help you today?",
        "es": "¡Bienvenido al estadio! ¿Cómo puedo ayudarte hoy?",
        "fr": "Bienvenue au stade ! Comment puis-je vous aider ?",
        "ar": "مرحبًا بكم في الملعب! كيف يمكنني مساعدتك اليوم؟",
        "pt": "Bem-vindo ao estádio! Como posso ajudar?",
        "de": "Willkommen im Stadion! Wie kann ich helfen?",
        "hi": "स्टेडियम में आपका स्वागत है! मैं आपकी कैसे मदद कर सकता हूँ?",
    },
    "route_intro": {
        "en": "Here is your route: {x}",
        "es": "Aquí está tu ruta: {x}",
        "fr": "Voici votre itinéraire : {x}",
        "ar": "إليك مسارك: {x}",
        "pt": "Aqui está a sua rota: {x}",
        "de": "Hier ist deine Route: {x}",
        "hi": "यह रहा आपका रास्ता: {x}",
    },
    "crowd_intro": {
        "en": "Live crowd update: {x}",
        "es": "Actualización de multitudes en vivo: {x}",
        "fr": "Mise à jour de l'affluence : {x}",
        "ar": "تحديث الازدحام المباشر: {x}",
        "pt": "Atualização de público ao vivo: {x}",
        "de": "Live-Auslastung: {x}",
        "hi": "लाइव भीड़ अपडेट: {x}",
    },
    "accessibility_note": {
        "en": "This route is fully step-free. Accessible restrooms and the sensory room are marked on your path.",
        "es": "Esta ruta es totalmente accesible, sin escalones. Los baños accesibles están señalizados.",
        "fr": "Cet itinéraire est entièrement sans marches. Les toilettes accessibles sont indiquées.",
        "ar": "هذا المسار خالٍ تمامًا من الدرج. دورات المياه الميسّرة محددة على طريقك.",
        "pt": "Esta rota é totalmente sem degraus. Banheiros acessíveis estão sinalizados.",
        "de": "Diese Route ist komplett stufenfrei. Barrierefreie Toiletten sind ausgeschildert.",
        "hi": "यह मार्ग पूरी तरह सीढ़ी-रहित है। सुलभ शौचालय आपके रास्ते पर चिह्नित हैं।",
    },
    "fallback": {
        "en": "I can help with directions, crowd levels, food, restrooms, first aid, transport and accessibility. Try: 'How do I get from Gate A to Section 115?'",
        "es": "Puedo ayudarte con direcciones, multitudes, comida, baños, primeros auxilios, transporte y accesibilidad.",
        "fr": "Je peux aider avec les itinéraires, l'affluence, la restauration, les toilettes, les premiers secours et l'accessibilité.",
        "ar": "يمكنني المساعدة في الاتجاهات ومستويات الازدحام والطعام ودورات المياه والإسعافات الأولية والنقل وإمكانية الوصول.",
        "pt": "Posso ajudar com direções, multidões, comida, banheiros, primeiros socorros, transporte e acessibilidade.",
        "de": "Ich helfe bei Wegbeschreibungen, Auslastung, Essen, Toiletten, Erster Hilfe, Transport und Barrierefreiheit.",
        "hi": "मैं दिशा-निर्देश, भीड़ स्तर, भोजन, शौचालय, प्राथमिक चिकित्सा, परिवहन और सुलभता में मदद कर सकता हूँ।",
    },
}


def phrase(key: str, language: str, x: str = "") -> str:
    """Localized phrase with graceful fallback to English."""
    table = PHRASES.get(key, {})
    template = table.get(language) or table.get("en", "")
    return template.replace("{x}", x)
