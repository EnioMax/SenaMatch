/**
 * Engine Matemática Otimizada - SenaMatch
 * Módulo de Probabilidades, Filtros Estatísticos e Espalhamento Combinatório
 */
const SenaEngine = {
  // Parâmetros baseados na distribuição histórica da Mega-Sena
  CONFIG: {
    somaMinima: 140,
    somaMaxima: 225,
    maxConsecutivos: 2, 
    maxMesmoFinal: 2,   
    paridadesAceitas: ['3:3', '4:2', '2:4'],
    maxPorQuadrante: 3
  },

  // 1. Validador de Filtros Estatísticos
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

  // 2. Cálculo de Interseção entre Dois Jogos
  calcularIntersecao(jogoA, jogoB) {
    const setB = new Set(jogoB);
    return jogoA.filter(n => setB.has(n)).length;
  },

  // 3. Gerador do Lote Otimizado de 64 Jogos
  gerarLoteOtimizado(poolDezenas = [], tamanhoLote = 64) {
    const universo = poolDezenas.length >= 18 
      ? poolDezenas 
      : Array.from({ length: 60 }, (_, i) => i + 1);

    const lote = [];
    let tentativas = 0;
    const maxTentativas = 40000;

    while (lote.length < tamanhoLote && tentativas < maxTentativas) {
      tentativas++;

      // Sorteia 6 dezenas do pool disponível
      const embaralhado = [...universo].sort(() => 0.5 - Math.random());
      const candidato = embaralhado.slice(0, 6).sort((a, b) => a - b);

      // Passa pelos filtros estatísticos
      if (!this.validarJogo(candidato)) continue;

      // Evita duplicatas exatas
      const chave = candidato.join('-');
      if (lote.some(j => j.join('-') === chave)) continue;

      // Aplica Espalhamento Combinatório
      if (lote.length > 0) {
        const sobreposicaoAlta = lote.some(j => this.calcularIntersecao(candidato, j) >= 4);
        if (sobreposicaoAlta && tentativas < maxTentativas * 0.85) {
          continue; 
        }
      }

      lote.push(candidato);
    }

    return lote;
  }
};