// ============================================================================
// Extract Data for Graph DB — patched
// Strips markdown fences, normalises xsd datatypes on literals, and
// injects any PREFIX declarations the SPARQL uses but forgot to declare
// (:, om:, prov:, rdf:, rdfs:, owl:, xsd:).
// ============================================================================

const rawInput = $json.output;

// 1. Remove ```sparql fences (case-insensitive)
let sparql = rawInput.replace(/```sparql|```/gi, '').trim();

// 2. Normalise xsd datatype IRIs → xsd: prefix
sparql = sparql.replace(
  /\^\^<http:\/\/www\.w3\.org\/2001\/XMLSchema#([a-zA-Z]+)>/g,
  '^^xsd:$1'
);

// 3. Strip datatype tags from numeric / boolean literals (Jena accepts native)
sparql = sparql.replace(/(\d+)\^\^xsd:integer/g,        '$1');
sparql = sparql.replace(/(\d+\.\d+)\^\^xsd:float/g,     '$1');
sparql = sparql.replace(/(true|false)\^\^xsd:boolean/g, '$1');
sparql = sparql.replace(/"(\d+)"\^\^xsd:integer/g,      '$1');
sparql = sparql.replace(/"(\d+\.\d+)"\^\^xsd:float/g,   '$1');
sparql = sparql.replace(/"(true|false)"\^\^xsd:boolean/g,'$1');

// 4. Inject any prefix declarations the body uses but did not declare.
//    Order matters: check body for usage, then prepend if missing.
const wanted = {
  ''    : '<http://ontology.company.com/telemetry#>',  // bare-colon default
  'om'  : '<http://ontology.company.com/telemetry#>',
  'prov': '<http://www.w3.org/ns/prov#>',
  'rdf' : '<http://www.w3.org/1999/02/22-rdf-syntax-ns#>',
  'rdfs': '<http://www.w3.org/2000/01/rdf-schema#>',
  'owl' : '<http://www.w3.org/2002/07/owl#>',
  'xsd' : '<http://www.w3.org/2001/XMLSchema#>'
};

const bodyStart = sparql.search(/\bINSERT\s+DATA\b|\bDELETE\s+DATA\b|\bWHERE\s*\{/i);
const header    = bodyStart >= 0 ? sparql.slice(0, bodyStart) : '';
const body      = bodyStart >= 0 ? sparql.slice(bodyStart)    : sparql;

const missingPrefixes = [];
for (const [p, iri] of Object.entries(wanted)) {
  // Is this prefix used in the body?
  const usageRe = p === ''
    ? /(?:^|[\s;,\.\{\(])(:[A-Za-z_][\w-]*)/     // bare-colon local names
    : new RegExp(`\\b${p}:[A-Za-z_][\\w-]*`);    // prefixed name
  const declRe  = new RegExp(`PREFIX\\s+${p}:`, 'i');
  if (usageRe.test(body) && !declRe.test(header)) {
    missingPrefixes.push(`PREFIX ${p}: ${iri}`);
  }
}

if (missingPrefixes.length) {
  sparql = missingPrefixes.join('\n') + '\n' + sparql;
}

// 5. Guarantee a leading rdf: prefix if header is empty entirely
if (!/^\s*PREFIX/i.test(sparql)) {
  sparql = 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n' + sparql;
}

return {
  json: {
    sparqlQuery: sparql
  }
};
