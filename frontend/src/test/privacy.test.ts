import { describe, expect, it } from 'vitest'
import html from '../../index.html?raw'

describe('privacy', () => {
  it('does not load fonts from third-party CDNs (visitor IP stays with us)', () => {
    expect(html).not.toMatch(/fonts\.(googleapis|gstatic)\.com/)
  })
})
