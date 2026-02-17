from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def create_dummy_pdf(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "WonderDrug Promotional Material")

    # Body Text
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, "WonderDrug is the best drug for everything.")
    c.drawString(50, height - 100, "It cures all ailments instantly.")

    # ISI Section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 150, "Important Safety Information")

    c.setFont("Helvetica", 10)
    text = c.beginText(50, height - 170)
    lines = [
        "Contraindications: Do not use WonderDrug if you are allergic to happiness.",
        "Warnings and Precautions: WonderDrug may cause excessive smiling.",
        "Adverse Reactions: The most common side effects include joy and relief.",
        "Drug Interactions: Do not take with sadness.",
        "Use in Specific Populations: Safe for everyone except grumps.",
    ]
    for line in lines:
        text.textLine(line)
    c.drawText(text)

    c.save()
    print(f"Created {filename}")


if __name__ == "__main__":
    create_dummy_pdf("dummy_isi.pdf")
