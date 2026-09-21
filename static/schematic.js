document.addEventListener('DOMContentLoaded', () => {
    if (typeof LiteGraph === 'undefined' || !document.getElementById('schematic-canvas')) return;

    // 1. Initialize LiteGraph
    const graph = new LGraph();
    const canvas = new LGraphCanvas("#schematic-canvas", graph);
    canvas.background_image = null;
    canvas.clear_background = true;
    canvas.clear_background_color = "#1b1b2f";
    
    // Auto-resize
    const resizeCanvas = () => {
        const parent = canvas.canvas.parentNode;
        canvas.resize(parent.clientWidth, parent.clientHeight);
    };
    window.addEventListener('resize', resizeCanvas);
    setTimeout(resizeCanvas, 100);

    LiteGraph.DEFAULT_SHADOW_COLOR = "rgba(0,0,0,0.5)";
    LiteGraph.WIDGET_TEXT_COLOR = "#fff";

    // 2. Define custom nodes
    const defineGateNode = (type, inPorts, outPorts, title, color, bgColor) => {
        function LogicNode() {
            inPorts.forEach(inp => this.addInput(inp, "boolean"));
            outPorts.forEach(out => this.addOutput(out, "boolean"));
            this.title = title;
            // Generate a unique starting label
            this.properties = { label: title + "_" + Math.floor(Math.random() * 1000) };
            this.color = color || "#2a2a4a";
            this.bgcolor = bgColor || "#1a1a2a";
            this.size = this.computeSize();
        }
        
        LogicNode.title = title;
        
        // Draw the label clearly
        LogicNode.prototype.onDrawTitle = function(ctx) {
            if (this.flags.collapsed) return;
            ctx.fillStyle = "#fff";
            ctx.font = "bold 12px Arial";
            ctx.textAlign = "center";
            ctx.fillText(this.properties.label, this.size[0] * 0.5, 14);
        };
        
        LogicNode.prototype.onPropertyChanged = function(name, value) {
            if (name === "label") this.properties.label = value;
            scheduleSync();
        };

        LiteGraph.registerNodeType(type, LogicNode);
    };

    defineGateNode("INPUT", [], ["out"], "INPUT", "#3a3a5c", "#2d2d47");
    defineGateNode("OUTPUT", ["in"], [], "OUTPUT", "#5c3a3a", "#472d2d");
    defineGateNode("AND", ["in0", "in1"], ["out"], "AND");
    defineGateNode("OR", ["in0", "in1"], ["out"], "OR");
    defineGateNode("NOT", ["in0"], ["out"], "NOT");
    defineGateNode("NAND", ["in0", "in1"], ["out"], "NAND");
    defineGateNode("NOR", ["in0", "in1"], ["out"], "NOR");
    defineGateNode("XOR", ["in0", "in1"], ["out"], "XOR");
    defineGateNode("XNOR", ["in0", "in1"], ["out"], "XNOR");
    defineGateNode("MUX2", ["a", "b", "sel"], ["out"], "MUX2");
    defineGateNode("MUX4", ["d0", "d1", "d2", "d3", "s0", "s1"], ["out"], "MUX4");
    defineGateNode("DEC2X4", ["a0", "a1", "en"], ["y0", "y1", "y2", "y3"], "DEC2X4");
    defineGateNode("DEC3X8", ["a0", "a1", "a2", "en"], ["y0", "y1", "y2", "y3", "y4", "y5", "y6", "y7"], "DEC3X8");

    // 3. Setup drag & drop
    document.querySelectorAll(".tool-item").forEach(item => {
        item.addEventListener("dragstart", (e) => {
            e.dataTransfer.setData("type", item.dataset.node);
            e.dataTransfer.effectAllowed = "copy";
        });
    });

    const canvasContainer = document.querySelector('.canvas-container');
    canvasContainer.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
    });

    canvasContainer.addEventListener("drop", (e) => {
        e.preventDefault();
        const type = e.dataTransfer.getData("type");
        if (type) {
            const node = LiteGraph.createNode(type);
            if (node) {
                const rect = canvas.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const graphCoords = canvas.convertOffsetToCanvas([x, y]);
                
                node.pos = [graphCoords[0], graphCoords[1]];
                
                if (type === "INPUT" || type === "OUTPUT") {
                    node.properties.label = "W_" + Math.floor(Math.random() * 100);
                } else {
                    node.properties.label = type + "_" + Math.floor(Math.random() * 100);
                }
                
                graph.add(node);
                canvas.setDirty(true, true);
                scheduleSync();
            }
        }
    });

    // 4. Double click to edit node label
    canvas.onNodeDoubleClicked = function(node) {
        const newLabel = prompt("Enter new name for this component:", node.properties.label);
        if (newLabel) {
            node.properties.label = newLabel.trim().toUpperCase().replace(/\s+/g, '_');
            canvas.setDirty(true, true);
            scheduleSync();
        }
    };

    // 5. Sync logic
    let syncTimeout = null;
    let isSyncing = false;
    let lastNetlistText = "";

    const statusEl = document.getElementById("sync-status");
    const netlistEditor = document.getElementById("live-netlist");
    const ttResults = document.getElementById("live-tt-results");

    function scheduleSync() {
        if (syncTimeout) clearTimeout(syncTimeout);
        statusEl.textContent = "Syncing...";
        statusEl.style.color = "var(--text-muted)";
        syncTimeout = setTimeout(syncSchematicToNetlist, 500);
    }

    graph.onNodeAdded = scheduleSync;
    graph.onNodeRemoved = scheduleSync;
    graph.onConnectionChange = scheduleSync;

    async function syncSchematicToNetlist() {
        if (isSyncing) return;
        isSyncing = true;
        
        try {
            const nodes = graph._nodes.map(n => ({
                id: "n" + n.id,
                type: n.type,
                label: n.properties.label,
                x: n.pos[0],
                y: n.pos[1]
            }));
            
            const wires = [];
            graph._nodes.forEach(n => {
                if (n.outputs) {
                    n.outputs.forEach((outPort, outIdx) => {
                        if (outPort.links) {
                            outPort.links.forEach(linkId => {
                                const link = graph.links[linkId];
                                if (link) {
                                    const toNode = graph.getNodeById(link.target_id);
                                    if (toNode) {
                                        wires.push({
                                            from: "n" + n.id,
                                            fromPort: outPort.name,
                                            to: "n" + link.target_id,
                                            toPort: toNode.inputs[link.target_slot].name
                                        });
                                    }
                                }
                            });
                        }
                    });
                }
            });

            const res = await fetch("/api/schematic/to-netlist", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nodes, wires })
            });

            const data = await res.json();
            if (data.netlist !== undefined) {
                if (netlistEditor.value !== data.netlist) {
                    netlistEditor.value = data.netlist;
                    lastNetlistText = data.netlist;
                }
                statusEl.textContent = "Synced ✓";
                statusEl.style.color = "var(--primary)";
                updateTruthTable(data.netlist);
            }
        } catch (e) {
            console.error(e);
            statusEl.textContent = "Sync Error";
            statusEl.style.color = "var(--error-color)";
        }
        isSyncing = false;
    }

    // 6. Netlist -> Schematic Sync
    netlistEditor.addEventListener("input", () => {
        if (syncTimeout) clearTimeout(syncTimeout);
        statusEl.textContent = "Syncing...";
        statusEl.style.color = "var(--text-muted)";
        syncTimeout = setTimeout(syncNetlistToSchematic, 800);
    });

    async function syncNetlistToSchematic() {
        if (isSyncing) return;
        const text = netlistEditor.value;
        if (text === lastNetlistText) return;
        
        isSyncing = true;
        try {
            const res = await fetch("/api/netlist/to-schematic", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ netlist: text })
            });
            
            const data = await res.json();
            if (data.error) {
                statusEl.textContent = "Invalid Netlist";
                statusEl.style.color = "var(--error-color)";
                ttResults.innerHTML = `<div class="error-msg">${data.error}</div>`;
            } else {
                graph.clear();
                const idMap = {};
                
                data.nodes.forEach(nData => {
                    const node = LiteGraph.createNode(nData.type);
                    if (node) {
                        node.pos = [nData.x, nData.y];
                        node.properties.label = nData.label;
                        graph.add(node);
                        idMap[nData.id] = node.id;
                    }
                });
                
                data.wires.forEach(wData => {
                    const fromNodeId = idMap[wData.from];
                    const toNodeId = idMap[wData.to];
                    
                    if (fromNodeId !== undefined && toNodeId !== undefined) {
                        const fromNode = graph.getNodeById(fromNodeId);
                        const toNode = graph.getNodeById(toNodeId);
                        
                        const outSlot = fromNode.outputs.findIndex(o => o.name === wData.fromPort);
                        const inSlot = toNode.inputs.findIndex(i => i.name === wData.toPort);
                        
                        if (outSlot !== -1 && inSlot !== -1) {
                            fromNode.connect(outSlot, toNode, inSlot);
                        }
                    }
                });
                
                lastNetlistText = text;
                statusEl.textContent = "Synced ✓";
                statusEl.style.color = "var(--primary)";
                canvas.setDirty(true, true);
                updateTruthTable(text);
            }
        } catch (e) {
            console.error(e);
            statusEl.textContent = "Sync Error";
            statusEl.style.color = "var(--error-color)";
        }
        isSyncing = false;
    }

    // 7. Auto-generate Truth Table
    async function updateTruthTable(netlistText) {
        if (!netlistText.trim()) {
            ttResults.innerHTML = '<p class="placeholder-text">Empty circuit</p>';
            return;
        }
        
        try {
            const res = await fetch("/api/netlist/truth-table", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ netlist: netlistText })
            });
            
            const data = await res.json();
            if (data.error) {
                ttResults.innerHTML = `<div class="error-msg">${data.error}</div>`;
                return;
            }
            
            if (data.rows.length === 0) {
                ttResults.innerHTML = '<p class="placeholder-text">No inputs/outputs defined</p>';
                return;
            }
            
            let html = '<table><thead><tr>';
            data.input_names.forEach(n => html += `<th>${n}</th>`);
            data.output_names.forEach(n => html += `<th>${n}</th>`);
            html += '</tr></thead><tbody>';
            
            data.rows.forEach(row => {
                html += '<tr>';
                data.input_names.forEach(n => html += `<td class="val-${row[n]}">${row[n]}</td>`);
                data.output_names.forEach(n => html += `<td class="val-${row[n]}">${row[n]}</td>`);
                html += '</tr>';
            });
            html += '</tbody></table>';
            
            ttResults.innerHTML = html;
        } catch (e) {
            ttResults.innerHTML = '<div class="error-msg">Failed to load truth table.</div>';
        }
    }

    // 8. Buttons
    document.getElementById("btn-clear-schematic").addEventListener("click", () => {
        graph.clear();
        scheduleSync();
    });

    document.getElementById("btn-copy-netlist").addEventListener("click", () => {
        navigator.clipboard.writeText(netlistEditor.value);
        alert("Netlist copied to clipboard!");
    });
    
    document.getElementById("btn-dl-netlist").addEventListener("click", () => {
        const blob = new Blob([netlistEditor.value], {type: "text/plain"});
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "circuit.net";
        a.click();
    });

    document.getElementById("btn-live-sim").addEventListener("click", async () => {
        const inputStr = document.getElementById("live-sim-inputs").value;
        const inputs = {};
        inputStr.split(",").forEach(part => {
            const [k, v] = part.split("=");
            if (k && v) inputs[k.trim()] = v.trim();
        });
        
        try {
            const res = await fetch("/api/netlist/simulate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ netlist: netlistEditor.value, inputs })
            });
            const data = await res.json();
            const resultsDiv = document.getElementById("live-sim-results");
            resultsDiv.classList.remove("empty");
            
            if (data.error) {
                resultsDiv.innerHTML = `<div class="error-msg">${data.error}</div>`;
            } else {
                let html = '<strong>Outputs:</strong><br>';
                for (const [k, v] of Object.entries(data.outputs)) {
                    html += `<div style="margin-top:0.25rem;">${k}: <span class="val-${v}">${v}</span></div>`;
                }
                resultsDiv.innerHTML = html;
            }
        } catch (e) {
            console.error(e);
        }
    });
});
