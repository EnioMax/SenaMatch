/**
 * Engine Matemática Otimizada - SenaMatch
 * Módulo de Probabilidades, Filtros Estatísticos e Espalhamento Combinatório
 */
const SenaEngine = {
  CONFIG: {
    somaMinima: 140,
    somaMaxima: 225,
    maxConsecutivos: 2, 
    maxMesmoFinal: 2,   
    paridadesAceitas: ['3:3', '4:2', '2:4'],
    maxPorQuadrante: 3
  },

  validarJogo(jogo) {
    const sorted = [...jogo].sort((a, b) => a - b);
    
    // A. Soma das Dezenas
    const soma = sorted.reduce((acc, val) => acc + val, 0);
    if (soma < this.CONFIG.somaMinima || soma > this.CONFIG.somaMaxima) return false;

    // B. Paridade (Pares e Ímpares)
    const pares = sorted.filter(n => n % 2 === 0).length;
    const impares = 6 - pares;
    if (!this.CONFIG.paridadesAceitas.includes(`${pares}:${impares}`)) return false;

    // C. Sequências Consecutivas
    let consecutivos = 1;
    for (let i = 0; i < sorted.length - 1; i++) {
      if (sorted[i + 1] === sorted[i] + 1) {
        consecutivos++;
        if (consecutivos > this.CONFIG.maxConsecutivos) return false;
      } else {
        consecutivos = 1;
      }
    }

    // D. Dígito Final (Terminações repetidas)
    const finais = {};
    for (const num of sorted) {
      const final = num % 10;
      finais[final] = (finais[final] || 0) + 1;
      if (finais[final] > this.CONFIG.maxMesmoFinal) return false;
    }

    // E. Distribuição por Quadrantes no Volante
    const quad = [0, 0, 0, 0];
    for (const num of sorted) {
      const linha = Math.floor((num - 1) / 10); 
      const coluna = (num - 1) % 10;           
      const idx = (linha < 3 ? 0 : 2) + (coluna < 5 ? 0 : 1);
      quad[idx]++;
      if (quad[idx] > this.CONFIG.maxPorQuadrante) return false;
    }

    return true;
  },

  // Fisher-Yates: embaralhamento uniforme (sort com Math.random é enviesado)
  embaralhar(lista) {
    const a = [...lista];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  },

  calcularIntersecao(jogoA, jogoB) {
    const setB = new Set(jogoB);
    return jogoA.filter(n => setB.has(n)).length;
  },

  gerarLoteOtimizado(poolDezenas = [], tamanhoLote = 64) {
    const universo = poolDezenas.length >= 18 
      ? poolDezenas 
      : Array.from({ length: 60 }, (_, i) => i + 1);

    const lote = [];
    let tentativas = 0;
    const maxTentativas = 50000;

    while (lote.length < tamanhoLote && tentativas < maxTentativas) {
      tentativas++;

      const embaralhado = this.embaralhar(universo);
      const candidato = embaralhado.slice(0, 6).sort((a, b) => a - b);

      if (!this.validarJogo(candidato)) continue;

      const chave = candidato.join('-');
      if (lote.some(j => j.join('-') === chave)) continue;

      if (lote.length > 0) {
        const sobreposicaoAlta = lote.some(j => this.calcularIntersecao(candidato, j) >= 4);
        if (sobreposicaoAlta && tentativas < maxTentativas * 0.85) {
          continue; 
        }
      }

      lote.push(candidato);
    }

    // Complementa com dezenas válidas caso atinja o limite de tentativas
    while (lote.length < tamanhoLote) {
      const embaralhado = this.embaralhar(universo);
      const candidato = embaralhado.slice(0, 6).sort((a, b) => a - b);
      const chave = candidato.join('-');
      if (!lote.some(j => j.join('-') === chave)) {
        lote.push(candidato);
      }
    }

    return lote;
  }
};

// Exportação explícita para visibilidade no escopo global (window)
window.SenaEngine = SenaEngine;