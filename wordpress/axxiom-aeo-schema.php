<?php
/**
 * Plugin Name: Axxiom AEO Schema
 * Description: AEO plumbing for Axxiom brand sites: JSON-LD output from post meta, robots.txt with sitemap + LLM policy, generated /llms.txt, and the IndexNow key file (Axxiom AEO Automation Platform).
 * Version: 1.2.0
 * Author: Axxiom Elevator
 *
 * Install: copy to wp-content/mu-plugins/axxiom-aeo-schema.php on each brand site.
 * NOTE: delete any physical robots.txt / llms.txt files at the web root — a
 * physical file is served before WordPress runs, which hides these endpoints.
 */

// Shared across all Axxiom brand sites; each host serves it at /<key>.txt,
// which is what makes IndexNow submissions for that host valid. Must match
// INDEXNOW_KEY on the AEO backend.
define('AXXIOM_INDEXNOW_KEY', 'c550d35adee3985871ee6e39bd7f8e35');

/**
 * Allow the Axxiom backend to write schema via WordPress REST API (meta.aeo_schema_json).
 */
add_action('init', function () {
    $args = [
        'type' => 'string',
        'single' => true,
        'show_in_rest' => true,
        'auth_callback' => function () {
            return current_user_can('edit_posts');
        },
    ];

    register_post_meta('post', 'aeo_schema_json', $args);
    register_post_meta('page', 'aeo_schema_json', $args);
});

add_action('wp_head', function () {
    if (!is_singular()) {
        return;
    }
    $post_id = get_queried_object_id();
    if (!$post_id) {
        return;
    }
    $schema = get_post_meta($post_id, 'aeo_schema_json', true);
    if (!$schema || !is_string($schema)) {
        return;
    }
    $schema = trim($schema);
    if ($schema === '') {
        return;
    }
    // Basic safety: only output if it looks like JSON object/array.
    if ($schema[0] !== '{' && $schema[0] !== '[') {
        return;
    }
    // '</' inside the JSON (e.g. '</script>' in a string) would end the block
    // early; '<\/' is a valid JSON escape, so the JSON-LD stays parseable.
    $schema = str_replace('</', '<\/', $schema);
    echo '<script type="application/ld+json">' . $schema . '</script>' . "\n";
}, 5);

/**
 * The sitemap URL for this site: Yoast's index when Yoast is active, else
 * WordPress core's wp-sitemap.xml.
 */
function axxiom_aeo_sitemap_url() {
    if (defined('WPSEO_VERSION')) {
        return home_url('/sitemap_index.xml');
    }
    return home_url('/wp-sitemap.xml');
}

/**
 * robots.txt: allow everything (including AI crawlers), declare the sitemap,
 * and point LLMs at /llms.txt. Only applies to WordPress's virtual
 * robots.txt — delete any physical robots.txt file so this takes effect.
 */
add_filter('robots_txt', function ($output) {
    $lines = [
        'User-agent: *',
        'Allow: /',
        '',
        'LLM-Policy: ' . home_url('/llms.txt'),
        'Sitemap: ' . axxiom_aeo_sitemap_url(),
    ];
    return trim($output) === '' ? implode("\n", $lines) . "\n"
        : rtrim($output) . "\n\n" . implode("\n", array_slice($lines, 3)) . "\n";
});

/**
 * Serve /llms.txt (generated) and /<indexnow-key>.txt. Handled before
 * template resolution so no theme/permalink setup is required. A physical
 * file with the same name at the web root wins (served before WP) — that's
 * fine, it just overrides the generated version.
 */
add_action('parse_request', function ($wp) {
    $path = trim(parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH) ?? '', '/');

    if ($path === AXXIOM_INDEXNOW_KEY . '.txt') {
        header('Content-Type: text/plain; charset=utf-8');
        echo AXXIOM_INDEXNOW_KEY;
        exit;
    }

    if ($path !== 'llms.txt') {
        return;
    }

    header('Content-Type: text/plain; charset=utf-8');
    $name = get_bloginfo('name');
    $desc = get_bloginfo('description');

    echo "# {$name}\n\n";
    if ($desc) {
        echo "> {$desc}\n\n";
    }
    echo "> Independent elevator service company. Content below answers common\n";
    echo "> elevator maintenance, repair, modernization, inspection, and\n";
    echo "> compliance questions for our service markets.\n\n";
    echo "Sitemap: " . axxiom_aeo_sitemap_url() . "\n\n";

    echo "## Key pages\n\n";
    $pages = get_pages(['sort_column' => 'menu_order', 'number' => 15]);
    foreach ($pages as $p) {
        echo '- [' . wp_strip_all_tags(get_the_title($p)) . '](' . get_permalink($p) . ")\n";
    }

    echo "\n## Articles\n\n";
    $posts = get_posts(['numberposts' => 100, 'post_status' => 'publish']);
    foreach ($posts as $p) {
        echo '- [' . wp_strip_all_tags(get_the_title($p)) . '](' . get_permalink($p) . ")\n";
    }
    exit;
});
