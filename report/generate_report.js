const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  PageBreak
} = require("docx");

const fs = require("fs");

function text(value, bold = false, size = 22) {
  return new TextRun({
    text: value,
    bold,
    size,
    font: "Arial"
  });
}

function heading(title, level = 1) {

  return new Paragraph({
    heading:
      level === 1
        ? HeadingLevel.HEADING_1
        : HeadingLevel.HEADING_2,

    spacing: {
      before: 200,
      after: 120
    },

    children: [
      new TextRun({
        text: title,
        bold: true,
        size: level === 1 ? 30 : 24,
        font: "Arial"
      })
    ]
  });
}

function para(content) {

  return new Paragraph({
    spacing: {
      after: 120
    },
    children: [
      text(content)
    ]
  });
}

function bullet(content) {

  return new Paragraph({
    bullet: {
      level: 0
    },

    spacing: {
      after: 80
    },

    children: [
      text(content)
    ]
  });
}

function codeBlock(lines) {

  return new Table({
    width: {
      size: 100,
      type: WidthType.PERCENTAGE
    },

    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders: {
              top: {
                style: BorderStyle.SINGLE,
                size: 1,
                color: "BBBBBB"
              },

              bottom: {
                style: BorderStyle.SINGLE,
                size: 1,
                color: "BBBBBB"
              },

              left: {
                style: BorderStyle.SINGLE,
                size: 1,
                color: "BBBBBB"
              },

              right: {
                style: BorderStyle.SINGLE,
                size: 1,
                color: "BBBBBB"
              }
            },

            children: lines.map(line =>
              new Paragraph({
                children: [
                  new TextRun({
                    text: line,
                    font: "Courier New",
                    size: 18
                  })
                ]
              })
            )
          })
        ]
      })
    ]
  });
}

const documentFile = new Document({

  sections: [
    {
      children: [

        new Paragraph({
          alignment: AlignmentType.CENTER,

          spacing: {
            after: 200
          },

          children: [
            new TextRun({
              text: "PDC Assignment 2",
              bold: true,
              size: 36
            })
          ]
        }),

        new Paragraph({
          alignment: AlignmentType.CENTER,

          spacing: {
            after: 400
          },

          children: [
            new TextRun({
              text: "Building Resilient Distributed Systems",
              size: 24
            })
          ]
        }),

        para("Student ID: BSAI23033"),

        heading("Part 1 - Analysis", 1),

        heading("Problem 1 - Concurrent Document Updates", 2),

        para(
          "The document update issue happens because two users can modify the same document at nearly the same time. Both users may read the same version of the document and send updates separately. Since there is no version checking in the basic implementation, the second request overwrites the first update."
        ),

        codeBlock([
          "doc = db.query(Document).first()",
          "doc.content = updated_text",
          "db.commit()"
        ]),

        para(
          "This causes inconsistent document data because the application cannot detect stale updates."
        ),

        heading("Problem 2 - Webhook Coordination Failure", 2),

        para(
          "Webhook events from Clerk can fail because of network interruptions or server downtime. Without idempotency handling, duplicate webhook deliveries may apply the same action multiple times."
        ),

        para(
          "If a cancellation event is missed entirely, the user's subscription state becomes inconsistent with the Clerk system."
        ),

        heading("Problem 3 - External AI Service Failure", 2),

        para(
          "The AI service request can become very slow or completely unavailable. If the FastAPI server waits for every request synchronously, server resources remain blocked."
        ),

        para(
          "Under heavy load this can make the entire backend unresponsive."
        ),

        new Paragraph({
          children: [new PageBreak()]
        }),

        heading("Part 2 - System Design", 1),

        heading("Optimistic Locking", 2),

        para(
          "The solution is to store a version number for each document. Every update request must include the version number that the user originally fetched."
        ),

        codeBlock([
          "if current_version != expected_version:",
          "    raise HTTPException(409)",
          "",
          "document.version += 1"
        ]),

        para(
          "If another user already updated the document, the versions will not match and the request will be rejected."
        ),

        heading("Webhook Idempotency", 2),

        para(
          "Each webhook event contains a unique identifier. Before processing a webhook, the backend checks whether the event ID already exists in the database."
        ),

        bullet("duplicate events are ignored"),
        bullet("new events are processed normally"),
        bullet("database constraints prevent duplicate inserts"),

        heading("Circuit Breaker Pattern", 2),

        para(
          "The circuit breaker prevents repeated calls to a failing AI service."
        ),

        bullet("CLOSED state allows normal requests"),
        bullet("OPEN state blocks requests after repeated failures"),
        bullet("RECOVERING state tests whether the service is healthy again"),

        codeBlock([
          "if failures >= limit:",
          "    state = OPEN",
          "",
          "return fallback_response"
        ]),

        para(
          "Instead of waiting for long AI timeouts, the system immediately returns a fallback response."
        ),

        heading("CAP Theorem Discussion", 2),

        para(
          "The document update solution prioritizes consistency over availability because conflicting updates are rejected."
        ),

        para(
          "The circuit breaker prioritizes availability because fallback responses are returned even when the AI service is unavailable."
        ),

        para(
          "These trade-offs improve overall reliability of the distributed system."
        ),

        heading("Implementation Summary", 2),

        para(
          "The implemented code demonstrates optimistic locking, webhook deduplication, and a circuit breaker for external AI service protection."
        ),

        para(
          "The circuit breaker implementation was tested using simulated AI service failures."
        )
      ]
    }
  ]
});

Packer.toBuffer(documentFile).then(buffer => {

  fs.writeFileSync(
    "./report/PDC_Assignment2_Report.docx",
    buffer
  );

  console.log("report generated");
});