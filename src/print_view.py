"""Shared Print View utility — opens a clean new window with only tables for printing."""
import streamlit.components.v1 as components


def print_button(title="Print View"):
    """Render a Print View button that opens a new browser tab with all tables."""
    # Use blob URL + anchor click to bypass popup blockers in Streamlit iframes
    components.html("""
    <button id="pvBtn" onclick="openPrintView()" style="background:#4a5568; color:white; border:none;
        padding:6px 16px; border-radius:4px; cursor:pointer; font-size:13px; font-family:Calibri,sans-serif;">
        &#128424; Print View
    </button>
    <script>
    function openPrintView() {
        try {
            var topDoc = window.top.document;

            var titleEl = topDoc.querySelector('.main [data-testid="stMarkdownContainer"] h1');
            var pageTitle = titleEl ? titleEl.textContent : '""" + title.replace("'", "\\'") + """';

            var container = topDoc.querySelector('[data-testid="stAppViewBlockContainer"]')
                || topDoc.querySelector('.main .block-container')
                || topDoc.querySelector('[data-testid="stMainBlockContainer"]')
                || topDoc.querySelector('.main')
                || topDoc.querySelector('[data-testid="stAppViewContainer"]')
                || topDoc.body;
            var tables = container.querySelectorAll('table');

            if (tables.length === 0) {
                alert('No tables found on this page.');
                return;
            }

            var content = '';
            tables.forEach(function(tbl) {
                var wrapper = tbl.closest('div[data-testid="stMarkdownContainer"]');
                var heading = '';
                if (wrapper) {
                    var prev = wrapper.parentElement;
                    while (prev && prev.previousElementSibling) {
                        prev = prev.previousElementSibling;
                        var h = prev.querySelector('h2, h3');
                        if (h) {
                            heading = '<h3 style="margin:18px 0 6px; color:#2d3748;">' + h.textContent + '</h3>';
                            break;
                        }
                        if (prev.querySelector('table')) break;
                    }
                }

                var clone = tbl.cloneNode(true);
                clone.querySelectorAll('th, td').forEach(function(cell) {
                    cell.style.position = 'static';
                    cell.style.zIndex = '';
                    cell.style.top = '';
                    cell.style.left = '';
                });
                clone.style.borderCollapse = 'collapse';
                clone.style.borderSpacing = '0';
                clone.style.width = '100%';
                clone.style.maxHeight = 'none';
                // Remove scroll wrapper if cloned inside one
                content += heading + '<div style="margin-bottom:24px;">' + clone.outerHTML + '</div>';
            });

            var html = '<!DOCTYPE html><html><head><meta charset="utf-8">' +
                '<title>' + pageTitle + '</title>' +
                '<style>' +
                '@page { size: landscape; margin: 8mm; }' +
                'body { font-family: Calibri, sans-serif; font-size: 10px; color: #2d3748; margin: 12px; }' +
                'h1 { font-size: 16px; margin-bottom: 8px; color: #1a202c; }' +
                'h3 { font-size: 12px; }' +
                'table { border-collapse: collapse; width: 100%; font-size: 9px; page-break-inside: auto; }' +
                'thead { display: table-header-group; }' +
                'tr { page-break-inside: avoid; }' +
                'th, td { padding: 2px 4px; }' +
                '.toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }' +
                '.toolbar button { padding: 6px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-family: Calibri, sans-serif; }' +
                '.btn-p { background: #4a5568; color: white; }' +
                '.btn-p:hover { background: #2d3748; }' +
                '.btn-c { background: #e2e8f0; color: #4a5568; }' +
                '.btn-c:hover { background: #cbd5e0; }' +
                '.ts { font-size: 11px; color: #718096; margin-left: auto; }' +
                '@media print { .toolbar { display: none !important; } }' +
                '</style></head><body>' +
                '<div class="toolbar">' +
                '<button class="btn-p" onclick="window.print()">&#128424; Print</button>' +
                '<button class="btn-c" onclick="window.close()">Close</button>' +
                '<span class="ts">' + new Date().toLocaleString() + '</span>' +
                '</div>' +
                '<h1>' + pageTitle + '</h1>' +
                content +
                '</body></html>';

            // Use blob URL + anchor click to bypass popup blockers
            var blob = new Blob([html], {type: 'text/html'});
            var url = URL.createObjectURL(blob);
            var a = topDoc.createElement('a');
            a.href = url;
            a.target = '_blank';
            a.rel = 'noopener';
            a.style.display = 'none';
            topDoc.body.appendChild(a);
            a.click();
            setTimeout(function() {
                topDoc.body.removeChild(a);
                URL.revokeObjectURL(url);
            }, 100);

        } catch(e) {
            alert('Print View error: ' + e.message);
        }
    }
    </script>
    """, height=40)
