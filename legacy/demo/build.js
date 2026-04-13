#!/usr/bin/node

/*
esbuild configuration.

Usage:
    npm run esbuild:build
    npm run esbuild:watch
*/

const esbuild = require('esbuild');
const copyStaticFiles = require('esbuild-copy-static-files');

const args = process.argv.slice(2);
const mode = args.includes('--watch') ? 'watch' : 'build';

const outputDir = process.env.DIST_DIR || `${__dirname}/demo/statics`;

const plugins = [
    copyStaticFiles({
        src: './assets/public',
        dest: `${outputDir}/public`,
        dereference: true,
        errorOnExist: false,
        preserveTimestamps: true,
        recursive: true,
    }),
];

async function main() {
    const context = await esbuild.context({
        entryPoints: [
            `${__dirname}/assets/main.js`,
        ],
        outdir: outputDir,
        target: 'esnext',
        format: 'esm',
        bundle: true,
        chunkNames: '[name]-[hash]',
        sourcemap: mode == "build" ? true : "inline",
        define: {},
        treeShaking: true,
        loader: {
            '.png': 'dataurl',
            '.jpg': 'file',
            '.jpeg': 'file',
            '.svg': 'file',
            '.gif': 'file',
        },
        plugins: plugins,
        minify: mode == 'build',
        external: ['/fonts/*', '/images/*'],
        logLevel: 'debug',
    });
    if (mode == 'watch') {
        await context.watch();
    } else {
        await context.rebuild();
        await context.dispose();
    }
}

main().catch((e) => {
    console.error(e);
    process.exit(1);
});
