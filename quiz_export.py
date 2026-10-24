"""Plain-text exports for quiz questions and end-of-session reports."""


def _letter(index: int) -> str:
    return chr(ord("A") + index) if 0 <= index < 26 else str(index + 1)


def format_quiz_export(quiz: dict) -> str:
    """Format a saved quiz as one copyable/printable plain-text document."""
    questions = quiz.get("questions") or []
    mode_labels = {
        "exam": "امتحان بالنقاط",
        "review_manual": "مراجعة سؤالًا بسؤال",
        "review_all": "نشر الاستفتاءات دفعة واحدة",
    }
    lines = [
        f"الاختبار #{quiz.get('id', '?')}: {quiz.get('title', 'اختبار')}",
        f"عدد الأسئلة: {len(questions)}",
        f"التصنيف: {quiz.get('category', 'عام')}",
        f"الصعوبة: {quiz.get('difficulty', 'medium')}",
        f"الوقت لكل سؤال: {quiz.get('seconds', 20)} ثانية",
        f"الطريقة: {mode_labels.get(quiz.get('mode', 'exam'), quiz.get('mode', 'exam'))}",
        "",
        "=" * 38,
    ]
    for number, question in enumerate(questions, 1):
        options = question.get("options") or []
        answer_index = question.get("answer", -1)
        lines.extend(["", f"السؤال {number}: {question.get('question', '')}"])
        lines.extend(f"  {_letter(index)}. {option}" for index, option in enumerate(options))
        if isinstance(answer_index, int) and 0 <= answer_index < len(options):
            lines.append(f"الإجابة الصحيحة: {_letter(answer_index)}. {options[answer_index]}")
        else:
            lines.append("الإجابة الصحيحة: غير متاحة")
        explanation = str(question.get("explanation", "") or "").strip()
        if explanation:
            lines.append(f"التفسير: {explanation}")
        lines.append("-" * 38)
    return "\n".join(lines).strip() + "\n"


def format_session_report(session: dict) -> str:
    """Format final scores (for competitive mode) and the answer key in one report."""
    questions = session.get("questions") or []
    mode = session.get("mode", "exam")
    title = str(session.get("quiz_title", "اختبار") or "اختبار")
    lines = [
        f"تقرير الاختبار: {title}",
        f"عدد الأسئلة: {len(questions)}",
        "النتائج النهائية" if mode == "exam" else "مفتاح إجابات المراجعة",
        "=" * 38,
    ]
    participants = sorted(
        (session.get("scores") or {}).values(),
        key=lambda row: (row.get("points", 0), row.get("correct", 0)),
        reverse=True,
    )
    if mode == "exam":
        if not participants:
            lines.append("لم تُسجّل أي إجابات.")
        else:
            for rank, row in enumerate(participants, 1):
                lines.append(
                    f"{rank}. {row.get('name', 'مشارك')} — "
                    f"{row.get('points', 0)} نقطة "
                    f"({row.get('correct', 0)}/{row.get('answered', 0)} صحيحة)"
                )
    lines.extend(["", "الأسئلة والخيارات والإجابات الصحيحة", "=" * 38])
    for number, question in enumerate(questions, 1):
        options = question.get("options") or []
        answer_index = question.get("answer", -1)
        lines.extend(["", f"السؤال {number}: {question.get('question', '')}"])
        lines.extend(f"  {_letter(index)}. {option}" for index, option in enumerate(options))
        if isinstance(answer_index, int) and 0 <= answer_index < len(options):
            lines.append(f"الإجابة الصحيحة: {_letter(answer_index)}. {options[answer_index]}")
        else:
            lines.append("الإجابة الصحيحة: غير متاحة")
        explanation = str(question.get("explanation", "") or "").strip()
        if explanation:
            lines.append(f"التفسير: {explanation}")
        lines.append("-" * 38)
    return "\n".join(lines).strip() + "\n"
