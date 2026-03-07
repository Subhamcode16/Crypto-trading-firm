/**
 * BFS Pathfinding — 4-connected grid, no diagonals.
 * Returns an array of {col, row} steps from start to end (EXCLUSIVE of start, INCLUSIVE of end).
 * Returns empty array if already at destination or no path found.
 *
 * @param {number} startCol
 * @param {number} startRow
 * @param {number} endCol
 * @param {number} endRow
 * @param {Set<string>} blockedTiles - Set of 'col,row' string keys
 * @param {number} mapCols - grid width
 * @param {number} mapRows - grid height
 */
export function findPath(startCol, startRow, endCol, endRow, blockedTiles, mapCols, mapRows) {
    const key = (c, r) => `${c},${r}`;

    if (startCol === endCol && startRow === endRow) return [];

    // BFS queue of {col, row, parent}
    const queue = [{ col: startCol, row: startRow, parent: null }];
    const visited = new Set([key(startCol, startRow)]);

    const DIRS = [
        { dc: 0, dr: -1 }, // up
        { dc: 0, dr: 1 }, // down
        { dc: -1, dr: 0 }, // left
        { dc: 1, dr: 0 }, // right
    ];

    let found = null;

    while (queue.length > 0) {
        const current = queue.shift();

        for (const { dc, dr } of DIRS) {
            const nc = current.col + dc;
            const nr = current.row + dr;
            const nk = key(nc, nr);

            if (nc < 0 || nr < 0 || nc >= mapCols || nr >= mapRows) continue;
            if (visited.has(nk)) continue;
            if (blockedTiles.has(nk)) continue;

            const node = { col: nc, row: nr, parent: current };
            visited.add(nk);

            if (nc === endCol && nr === endRow) {
                found = node;
                break;
            }
            queue.push(node);
        }
        if (found) break;
    }

    if (!found) return [];

    // Reconstruct path
    const path = [];
    let node = found;
    while (node.parent !== null) {
        path.unshift({ col: node.col, row: node.row });
        node = node.parent;
    }
    return path;
}

/**
 * Returns a list of all walkable {col, row} tiles on the map.
 * A tile is walkable if it is NOT in the blockedTiles set.
 */
export function getWalkableTiles(mapCols, mapRows, blockedTiles) {
    const tiles = [];
    for (let r = 0; r < mapRows; r++) {
        for (let c = 0; c < mapCols; c++) {
            if (!blockedTiles.has(`${c},${r}`)) {
                tiles.push({ col: c, row: r });
            }
        }
    }
    return tiles;
}
