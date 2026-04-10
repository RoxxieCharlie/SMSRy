$outputPdf = Join-Path $PSScriptRoot "SMS_Render_QA_Checklist.pdf"
$sections = @(
    @{
        Title = "A. Deployment Health"
        Items = @(
            "Open the Render live URL.",
            "Confirm the landing page loads.",
            "Confirm CSS and layout load correctly.",
            "Confirm there is no 502, 500, or blank screen.",
            "Open Render logs and confirm startup completed.",
            "Confirm there are no recurring database connection errors.",
            "Confirm there are no static files manifest errors.",
            "Confirm there are no websocket startup errors."
        )
    },
    @{
        Title = "B. Login"
        Items = @(
            "Open /login/.",
            "Confirm the login page is styled correctly.",
            "Confirm SMS and Smart Management Solution appear correctly.",
            "Log in with a valid account.",
            "Log in with an invalid password.",
            "Confirm invalid login shows a clean error.",
            "Refresh the login page and try again.",
            "Confirm there is no CSRF failure page."
        )
    },
    @{
        Title = "C. Staff Role"
        Items = @(
            "Log in as staff.",
            "Confirm staff dashboard opens.",
            "Confirm sidebar shows Dashboard, Request History, Requests.",
            "Confirm restricted storekeeper pages are blocked.",
            "Open /requests/.",
            "Confirm KPI cards are visible.",
            "Click Draft, Submitted, Fulfilled, and Locked KPI cards.",
            "Confirm clicked KPI glows and scales.",
            "Confirm workspace summary results change with the selected KPI.",
            "Confirm recent activity is visible.",
            "Confirm request history nav item opens the request history table page.",
            "Confirm request history KPI filters work.",
            "Confirm selected KPI glows and scales there too."
        )
    },
    @{
        Title = "D. Staff Request Flow"
        Items = @(
            "Create a new request.",
            "Add one item.",
            "Save as draft.",
            "Re-open and edit the draft.",
            "Add multiple items.",
            "Submit the request.",
            "Confirm submitted request appears in request history.",
            "Confirm submitted request cannot be edited like a draft anymore.",
            "Confirm fulfilled request becomes read-only after storekeeper action."
        )
    },
    @{
        Title = "E. Storekeeper Role"
        Items = @(
            "Log in as storekeeper.",
            "Confirm storekeeper dashboard opens.",
            "Confirm sidebar shows inventory, issuance history, stock-in history, requests, stock-in.",
            "Open /requests/.",
            "Confirm incoming requests queue loads.",
            "Click Pending Requests, Editable Fulfilled, Fulfilled Today, and Total Fulfilled.",
            "Confirm selected KPI glows and scales.",
            "Confirm results below match the selected KPI."
        )
    },
    @{
        Title = "F. Fulfillment Flow"
        Items = @(
            "Open a submitted request from queue.",
            "Confirm it goes to the fulfill page, not generic edit page.",
            "Confirm In Stock is visible on the fulfill page.",
            "Confirm request details are correct.",
            "Fulfill the request.",
            "Confirm success redirect works.",
            "Confirm success message appears.",
            "Confirm request disappears from pending queue.",
            "Confirm it appears in issuance history."
        )
    },
    @{
        Title = "G. Fulfillment Edit Flow"
        Items = @(
            "Open an editable fulfilled request.",
            "Increase quantity within allowed original requested cap.",
            "Reduce quantity.",
            "Try increasing beyond allowed cap.",
            "Confirm validation blocks invalid increase.",
            "Confirm save succeeds for valid changes.",
            "Confirm redirect goes back to request page.",
            "Confirm recent activity says item was increased or reduced.",
            "Confirm issuance history status shows Edited."
        )
    },
    @{
        Title = "H. Inventory"
        Items = @(
            "Open inventory as storekeeper.",
            "Search for an item.",
            "Filter All, Low, and Out.",
            "Confirm results change correctly.",
            "Confirm inventory decreases after fulfillment.",
            "Confirm inventory increases after stock-in.",
            "Confirm non-authorized users cannot access store inventory page."
        )
    },
    @{
        Title = "I. Stock-In"
        Items = @(
            "Open stock-in page.",
            "Confirm no stray symbols or empty top-right circles.",
            "Add one item.",
            "Add multiple rows.",
            "Increase and decrease stock-in quantity.",
            "Remove a row.",
            "Add optional comment.",
            "Upload optional document if used.",
            "Save stock-in.",
            "Confirm success.",
            "Confirm inventory updated.",
            "Confirm stock-in history recorded it."
        )
    },
    @{
        Title = "J. Issuance History"
        Items = @(
            "Open issuance history as storekeeper.",
            "Open issuance history as management.",
            "Filter by Today, Locked, and Edited.",
            "Confirm selected KPI glows and scales.",
            "Confirm requester column appears correctly.",
            "Confirm edited rows show Edited.",
            "Confirm quantities and items are correct."
        )
    },
    @{
        Title = "K. Stock-In History"
        Items = @(
            "Open stock-in history.",
            "Confirm records appear.",
            "Confirm quantities, comments, dates, and users are correct.",
            "Confirm latest stock-in appears without manual refresh if live update is active."
        )
    },
    @{
        Title = "L. Management Role"
        Items = @(
            "Log in as management.",
            "Confirm management dashboard opens.",
            "Confirm management can access history and report pages.",
            "Confirm management cannot use storekeeper-only action pages if that is intended.",
            "Open weekly report.",
            "Confirm item breakdown appears first.",
            "Confirm department summary appears next.",
            "Confirm totals are correct.",
            "Export Excel.",
            "Open exported file.",
            "Confirm title is SMS WEEKLY REPORT.",
            "Confirm report period and generated date are clearly visible.",
            "Confirm serial numbers are centered.",
            "Confirm total issued columns are centered.",
            "Confirm department summary sheet is present."
        )
    },
    @{
        Title = "M. Live Update / WebSocket"
        Items = @(
            "Open one staff page in browser tab 1.",
            "Open one storekeeper page in browser tab 2.",
            "Submit a request from staff.",
            "Confirm storekeeper request queue updates without refresh.",
            "Fulfill request from storekeeper.",
            "Confirm staff request and activity update without refresh.",
            "Perform stock-in.",
            "Confirm inventory or history pages update without refresh.",
            "Edit fulfillment.",
            "Confirm history and activity update without refresh."
        )
    },
    @{
        Title = "N. Production Safety Checks"
        Items = @(
            "Confirm HTTPS is working.",
            "Confirm no CSRF host or origin issues.",
            "Confirm no DisallowedHost error.",
            "Confirm no 404 on static CSS or JS.",
            "Confirm no websocket mixed-content errors in browser console.",
            "Confirm database-backed pages open normally after redeploy."
        )
    },
    @{
        Title = "O. Final Acceptance"
        Items = @(
            "Staff can create and submit requests.",
            "Storekeeper can fulfill and edit fulfillment.",
            "Inventory updates correctly.",
            "History pages reflect actions correctly.",
            "Excel weekly report exports properly.",
            "Live updates work.",
            "No critical production errors in Render logs."
        )
    }
)

$word = $null
$doc = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $doc = $word.Documents.Add()

    $selection = $word.Selection
    $selection.Style = "Normal"
    $selection.Font.Name = "Calibri"
    $selection.Font.Size = 11

    $selection.ParagraphFormat.Alignment = 1
    $selection.Font.Size = 18
    $selection.Font.Bold = 1
    $selection.TypeText("SMS Render QA Checklist")
    $selection.TypeParagraph()

    $selection.Font.Size = 10
    $selection.Font.Bold = 0
    $selection.TypeText("Printable post-deployment verification checklist")
    $selection.TypeParagraph()
    $selection.TypeText("Generated: " + (Get-Date -Format "dd MMM yyyy HH:mm"))
    $selection.TypeParagraph()
    $selection.TypeParagraph()

    foreach ($section in $sections) {
        $selection.ParagraphFormat.Alignment = 0
        $selection.Font.Name = "Calibri"
        $selection.Font.Size = 13
        $selection.Font.Bold = 1
        $selection.TypeText($section.Title)
        $selection.TypeParagraph()

        $selection.Font.Size = 11
        $selection.Font.Bold = 0

        foreach ($item in $section.Items) {
            $selection.TypeText([char]0x2022 + " " + $item)
            $selection.TypeParagraph()
        }

        $selection.TypeParagraph()
    }

    $wdExportFormatPDF = 17

    $doc.ExportAsFixedFormat($outputPdf.ToString(), $wdExportFormatPDF)
}
finally {
    if ($doc -ne $null) {
        $doc.Close([ref]$false)
    }
    if ($word -ne $null) {
        $word.Quit()
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}

Write-Output $outputPdf
