from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER


def generate_pdf(
    content: str,
    filename: str = "generated_report.pdf",
    title: str = "Sovereign AI Report",
    bottom_text: str = ""
) -> str:

    try:
        # Project root
        PROJECT_ROOT = Path(__file__).resolve().parents[3]

        # Keep generated PDFs inside data folder
        data_dir = (PROJECT_ROOT / "data").resolve()
        pdf_dir = (data_dir / "generated_pdfs").resolve()

        pdf_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # Prevent unsafe filenames
        safe_filename = Path(filename).name

        if not safe_filename.lower().endswith(".pdf"):
            safe_filename += ".pdf"

        output_path = (
            pdf_dir / safe_filename
        ).resolve()

        # Ensure output stays inside generated_pdfs
        try:
            output_path.relative_to(pdf_dir)
        except ValueError:
            return "Error: Invalid PDF output path."

        # PDF document
        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )

        styles = getSampleStyleSheet()

        title_style = styles["Title"]
        title_style.alignment = TA_CENTER

        body_style = styles["BodyText"]
        body_style.leading = 16

        story = []

        # Title
        story.append(
            Paragraph(
                title,
                title_style
            )
        )

        story.append(
            Spacer(1, 20)
        )

        # Content
        for line in str(content).splitlines():

            line = line.strip()

            if not line:
                story.append(
                    Spacer(1, 8)
                )
                continue

            # Escape characters that can break ReportLab markup
            line = (
                line
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            story.append(
                Paragraph(
                    line,
                    body_style
                )
            )

            story.append(
                Spacer(1, 6)
            )

        # Build PDF
        def add_bottom_text(canvas, doc):
             if bottom_text:
                  canvas.saveState()
                  canvas.setFont("Helvetica", 10)
                  canvas.drawCentredString(
                      A4[0] / 2,
                      30,
                      bottom_text
                  )
                  canvas.restoreState()


        document.build(
            story,
            onFirstPage=add_bottom_text,
            onLaterPages=add_bottom_text
        )

        return (
            f"PDF successfully created: "
            f"{output_path}"
        )

    except Exception as e:

        return (
            f"PDF generation error: {str(e)}"
        )