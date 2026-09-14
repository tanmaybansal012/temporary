document.addEventListener('DOMContentLoaded', () => {
    
    // Tab switching logic
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
        });
    });

    // Helper to format values with colors
    const formatValue = (val) => {
        const cls = val === 'Signal.HIGH' || val === '1' ? 'val-1' : 
                    val === 'Signal.LOW' || val === '0' ? 'val-0' : 'val-X';
        const display = val === 'Signal.HIGH' ? '1' : 
                        val === 'Signal.LOW' ? '0' : 
                        val === 'Signal.UNKNOWN' ? 'X' : val;
        return `<span class="${cls}">${display}</span>`;
    };

    // Helper for API calls
    const fetchApi = async (url, payload, btn, btnText) => {
        btn.innerHTML = '<span class="loading"></span>';
        btn.disabled = true;
        
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Unknown error');
            return data;
        } catch (err) {
            return { error: err.message };
        } finally {
            btn.innerHTML = btnText;
            btn.disabled = false;
        }
    };

    // Simulate Tab
    document.getElementById('btn-simulate').addEventListener('click', async (e) => {
        const btn = e.target;
        const netlist = document.getElementById('sim-netlist').value;
        const inputsStr = document.getElementById('sim-inputs').value;
        
        const inputs = {};
        if (inputsStr.trim()) {
            inputsStr.split(',').forEach(p => {
                const [k, v] = p.split('=');
                if (k && v) inputs[k.trim()] = v.trim();
            });
        }

        const resPanel = document.getElementById('sim-results');
        const data = await fetchApi('/api/simulate', { netlist, inputs }, btn, 'Simulate Circuit');

        resPanel.classList.remove('empty');
        if (data.error) {
            resPanel.innerHTML = `<div class="error-msg">${data.error}</div>`;
            return;
        }

        let html = '<h3 style="color:var(--text-muted); font-size:0.85rem; margin-bottom:0.5rem">Inputs</h3>';
        Object.entries(data.inputs).forEach(([k, v]) => {
            html += `<div class="data-kv"><span class="data-key">${k}</span><span>${formatValue(v)}</span></div>`;
        });
        
        html += '<h3 style="color:var(--text-muted); font-size:0.85rem; margin:1.5rem 0 0.5rem 0">Outputs</h3>';
        Object.entries(data.outputs).forEach(([k, v]) => {
            html += `<div class="data-kv"><span class="data-key">${k}</span><span>${formatValue(v)}</span></div>`;
        });
        
        resPanel.innerHTML = html;
    });

    // Truth Table Tab
    document.getElementById('btn-truth-table').addEventListener('click', async (e) => {
        const btn = e.target;
        const netlist = document.getElementById('tt-netlist').value;
        
        const resPanel = document.getElementById('tt-results');
        const data = await fetchApi('/api/truth-table', { netlist }, btn, 'Generate Truth Table');

        resPanel.classList.remove('empty');
        if (data.error) {
            resPanel.innerHTML = `<div class="error-msg">${data.error}</div>`;
            return;
        }

        let table = '<table><thead><tr>';
        data.input_names.forEach(n => table += `<th>${n}</th>`);
        data.output_names.forEach(n => table += `<th>${n}</th>`);
        table += '</tr></thead><tbody>';

        data.rows.forEach(row => {
            table += '<tr>';
            data.input_names.forEach(n => table += `<td>${formatValue(row[n])}</td>`);
            data.output_names.forEach(n => table += `<td>${formatValue(row[n])}</td>`);
            table += '</tr>';
        });
        table += '</tbody></table>';
        
        resPanel.innerHTML = table;
    });

    // Flip-Flop Tab
    document.getElementById('btn-flipflop').addEventListener('click', async (e) => {
        const btn = e.target;
        const type = document.getElementById('ff-type').value;
        const cycles = document.getElementById('ff-cycles').value;
        
        const wfPanel = document.getElementById('ff-waveform');
        const tablePanel = document.getElementById('ff-table');
        
        const data = await fetchApi('/api/demo-flipflop', { type, cycles }, btn, 'Run Simulation');

        wfPanel.classList.remove('empty');
        tablePanel.classList.remove('empty');

        if (data.error) {
            wfPanel.innerHTML = `<div class="error-msg">${data.error}</div>`;
            tablePanel.innerHTML = '';
            return;
        }

        wfPanel.innerHTML = `<img src="${data.image_b64}" alt="Waveform">`;

        let tablesHtml = '<h3 style="color:var(--text-muted); font-size:0.85rem; margin-bottom:0.5rem">Trace</h3>';
        tablesHtml += '<table><thead><tr>';
        data.trace_columns.forEach(c => tablesHtml += `<th>${c}</th>`);
        tablesHtml += '</tr></thead><tbody>';
        data.trace.forEach(row => {
            tablesHtml += '<tr>';
            data.trace_columns.forEach(c => tablesHtml += `<td>${formatValue(row[c])}</td>`);
            tablesHtml += '</tr>';
        });
        tablesHtml += '</tbody></table>';

        if (data.stt && data.stt.length > 0) {
            tablesHtml += '<h3 style="color:var(--text-muted); font-size:0.85rem; margin:1.5rem 0 0.5rem 0">State Transitions</h3>';
            tablesHtml += '<table><thead><tr>';
            data.stt_columns.forEach(c => tablesHtml += `<th>${c}</th>`);
            tablesHtml += '</tr></thead><tbody>';
            data.stt.forEach(row => {
                tablesHtml += '<tr>';
                data.stt_columns.forEach(c => tablesHtml += `<td>${formatValue(row[c])}</td>`);
                tablesHtml += '</tr>';
            });
            tablesHtml += '</tbody></table>';
        }

        tablePanel.innerHTML = tablesHtml;
    });

    // Universal Gates Tab
    document.getElementById('btn-gates').addEventListener('click', async (e) => {
        const btn = e.target;
        const gate = document.getElementById('ug-gate').value;
        const using = document.getElementById('ug-using').value;
        
        const resPanel = document.getElementById('ug-results');
        const data = await fetchApi('/api/verify-conversion', { gate, using }, btn, 'Verify Equivalence');

        resPanel.classList.remove('empty');
        if (data.error) {
            resPanel.innerHTML = `<div class="error-msg">${data.error}</div>`;
            return;
        }

        let html = '<table><thead><tr>';
        html += '<th>A</th>';
        if (!data.is_unary) html += '<th>B</th>';
        html += `<th>Native ${gate.toUpperCase()}</th>`;
        html += `<th>${using.toUpperCase()} Impl</th>`;
        html += '<th>Result</th>';
        html += '</tr></thead><tbody>';

        data.rows.forEach(row => {
            html += '<tr>';
            html += `<td>${formatValue(row.A)}</td>`;
            if (!data.is_unary) html += `<td>${formatValue(row.B)}</td>`;
            html += `<td>${formatValue(row.Native)}</td>`;
            html += `<td>${formatValue(row.Converted)}</td>`;
            
            const matchCls = row.Match === 'OK' ? 'match-ok' : 'match-fail';
            html += `<td class="${matchCls}">${row.Match === 'OK' ? '✓ MATCH' : '✗ FAIL'}</td>`;
            html += '</tr>';
        });
        html += '</tbody></table>';
        
        if (data.all_match) {
            html += `<div style="margin-top: 1rem; padding: 1rem; background: rgba(0, 212, 170, 0.1); border: 1px solid rgba(0, 212, 170, 0.3); border-radius: 8px; color: var(--primary); font-weight: 500;">✓ PASS — ${using.toUpperCase()}-built ${gate.toUpperCase()} is equivalent to native ${gate.toUpperCase()}.</div>`;
        }
        
        resPanel.innerHTML = html;
    });
});
